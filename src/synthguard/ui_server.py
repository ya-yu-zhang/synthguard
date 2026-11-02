"""Local web UI: generate scene batches, browse and curate them, edit `.env`, check a machine.

Standard library only (http.server), so it runs on an offline intranet machine with the
same lock file. One generation job at a time; it runs `synthguard scenes` in a child
process, so cancelling never leaves this server in a bad state.

Safety: binds to 127.0.0.1 by default. With --host 0.0.0.0 colleagues can generate and
browse, but only browsers on this machine may rewrite `.env` unless
--allow-remote-config is given. POSTs must be same-origin JSON (no cross-site requests
from other web pages), and the Host header must be an IP, localhost, this machine's
name or an --allow-host name (no DNS rebinding). There is no login: LAN use only.
"""
from __future__ import annotations

import collections
import importlib.metadata
import ipaddress
import json
import mimetypes
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from . import gen_client as gc
from . import scenes
from .records import imread, imwrite, load_yaml
from .settings import Settings, get_settings, repo_root

STATIC = Path(__file__).with_name("ui_static")  # built from web/ by `npm run build`, committed
PROGRESS = re.compile(r"^\[scenes\] (\d+)/(\d+) (\S+)")
ERROR = re.compile(r"^\[scenes\] (\S+): ")
THUMB = 480

# .env fields the UI edits: key, label, group, help. Order = form order.
ENV_FIELDS = [
    ("COMFY_URL", "ComfyUI 地址", "gen", "生图服务的地址和端口，Comfy 启动日志里能看到"),
    ("GEN_PROFILE", "生图配置", "gen", "configs/gen_<名字>.yaml，决定用哪套模型文件"),
    ("SYNTHGUARD_DATA_ROOT", "数据目录", "gen", "生成的图片存在这里；相对路径按仓库根目录算。每 100 张约 150 MB"),
    ("COMFY_ROOT", "ComfyUI 安装目录", "gen", "仅作记录，方便排查模型放在哪"),
    ("TRAIN_DEVICES", "训练用显卡", "exp", "检测实验用。单卡填 0，双卡 3090 填 1"),
    ("CUDA_VISIBLE_DEVICES", "Comfy 用显卡", "exp", "启动 Comfy 时用的显卡编号"),
    ("SKIP_DIFFUSION", "检测实验跳过扩散", "exp", "1 = E0/E2 实验不调用扩散模型；不影响这里的生图"),
    ("HF_ENDPOINT", "Hugging Face 镜像", "exp", "下载公开数据集用，例如 https://hf-mirror.com；可留空"),
]
ENV_KEYS = [f[0] for f in ENV_FIELDS]
HOST_REFUSED = ("用这个地址打开不被允许。请用机器名或 IP 访问；"
                "如果要用别的域名，启动时加 --allow-host <域名>")


def spec_name(value) -> str:
    """Scene spec names map to configs/scenes_<name>.yaml; never let them carry a path."""
    name = str(value or "")
    if not re.fullmatch(r"[a-z0-9_]{1,40}", name):
        raise ValueError("场景名不对")
    return name


# ---------------------------------------------------------------- .env file
def env_path() -> Path:
    return repo_root() / ".env"


def read_env() -> dict[str, str]:
    p = env_path()
    out: dict[str, str] = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def write_env(values: dict[str, str]) -> None:
    """Update keys in place, keep comments and unknown keys, append new keys at the end."""
    p = env_path()
    src = p if p.exists() else repo_root() / ".env.example"
    lines = src.read_text(encoding="utf-8").splitlines() if src.exists() else []
    todo = dict(values)
    out = []
    for line in lines:
        k = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if k in todo:
            out.append(f"{k}={todo.pop(k)}")
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in todo.items()]
    p.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    get_settings.cache_clear()


def gen_profiles() -> list[str]:
    return sorted(p.stem[4:] for p in (repo_root() / "configs").glob("gen_*.yaml"))


def validate_env(v: dict[str, str]) -> list[str]:
    errs = []
    if not re.match(r"^https?://[^\s/]+(:\d+)?/?$", v.get("COMFY_URL", "")):
        errs.append("ComfyUI 地址要像 http://127.0.0.1:8188 这样")
    if v.get("GEN_PROFILE") not in gen_profiles():
        errs.append(f"生图配置只能是：{', '.join(gen_profiles())}")
    if not v.get("SYNTHGUARD_DATA_ROOT"):
        errs.append("数据目录不能为空")
    if v.get("SKIP_DIFFUSION", "0") not in ("0", "1"):
        errs.append("检测实验跳过扩散只能是 0 或 1")
    for k, val in v.items():
        if "\n" in val or "\r" in val:
            errs.append(f"{k} 不能包含换行")
    return errs


# ---------------------------------------------------------------- health checks
def _check(cid, label, status, detail, fix=""):
    return {"id": cid, "label": label, "status": status, "detail": detail, "fix": fix}


def gpus() -> list[dict]:
    """nvidia-smi rather than torch: importing torch.cuda here would hold VRAM on every GPU."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    try:
        out = subprocess.run([exe, "--query-gpu=index,name,memory.total,memory.used",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True,
                             timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    rows = []
    for line in out.strip().splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) == 4:
            rows.append({"index": int(parts[0]), "name": parts[1],
                         "total_gb": round(int(parts[2]) / 1024, 1), "used_gb": round(int(parts[3]) / 1024, 1)})
    return rows


def health() -> list[dict]:
    s = get_settings()
    checks = []
    checks.append(_check("env", "配置文件", "ok" if env_path().exists() else "fail",
                         ".env 已存在" if env_path().exists() else "还没有 .env",
                         "" if env_path().exists() else "在下面填好配置并保存，就会生成 .env"))
    g = gpus()
    checks.append(_check("gpu", "显卡", "ok" if g else "warn",
                         "；".join(f"GPU {x['index']} {x['name']} {x['total_gb']} GB（已用 {x['used_gb']}）" for x in g)
                         or "没有找到 nvidia-smi",
                         "" if g else "确认已安装 NVIDIA 驱动；没有显卡也能浏览结果，但不能生图"))
    try:
        torch_v = importlib.metadata.version("torch")
    except importlib.metadata.PackageNotFoundError:
        torch_v = None
    checks.append(_check("python", "Python 环境", "ok" if torch_v else "fail",
                         f"Python {sys.version.split()[0]} · torch {torch_v or '未安装'}",
                         "" if torch_v else "按 REPRO.md 第 2 节用锁定文件重建 .venv"))
    prof_ok, weights = False, {}
    try:
        weights = load_yaml(f"gen_{s.gen_profile}")["weights"].get("krea2") or {}
        prof_ok = bool(weights)
    except FileNotFoundError:
        pass
    checks.append(_check("profile", "生图配置", "ok" if prof_ok else "fail",
                         f"gen_{s.gen_profile}.yaml" + ("" if prof_ok else " 不存在或缺少 weights.krea2"),
                         "" if prof_ok else "把生图配置改成 dev_5070 或 deploy_3090"))
    st = gc.probe(s.comfy_url)
    if st is None:
        checks.append(_check("comfy", "ComfyUI 连接", "fail", f"连不上 {s.comfy_url}",
                             "先启动 ComfyUI（例如在它的目录里运行 python main.py --port 8188），并确认端口和这里一致"))
        checks.append(_check("weights", "Krea 2 模型文件", "skip", "ComfyUI 连上后才能检查", ""))
    else:
        sysinfo = st.get("system", {})
        # "cuda:0 NVIDIA GeForce RTX 5070 : cudaMallocAsync" -> "NVIDIA GeForce RTX 5070"
        dev = ", ".join(re.sub(r"^cuda:\d+\s*|\s*:.*$", "", d.get("name", ""))
                        for d in st.get("devices", []))
        checks.append(_check("comfy", "ComfyUI 连接", "ok",
                             f"ComfyUI {sysinfo.get('comfyui_version', '?')} · {dev}", ""))
        folders = {"unet": ("diffusion_models", "unet"), "text_encoder": ("text_encoders", "clip"),
                   "vae": ("vae",)}
        missing = []
        for key, fs in folders.items():
            name = weights.get(key)
            if name and not any(name in gc.list_models(s.comfy_url, f) for f in fs):
                missing.append(f"models/{fs[0]}/{name}")
        checks.append(_check("weights", "Krea 2 模型文件", "fail" if missing or not weights else "ok",
                             ("缺少：" + "，".join(missing)) if missing else
                             ("、".join(weights.values()) if weights else "生图配置里没有模型"),
                             "把缺少的文件放进 Comfy 对应目录后，重启 Comfy 或在 Comfy 里刷新" if missing else ""))
    root = s.data_root
    try:
        probe_dir = root if root.exists() else root.parent
        free = shutil.disk_usage(probe_dir).free / 1e9
        writable = os.access(probe_dir, os.W_OK)
        status = "fail" if not writable else ("warn" if free < 20 else "ok")
        checks.append(_check("data", "数据目录", status,
                             f"{root} · 剩余 {free:.0f} GB" + ("" if root.exists() else "（首次生成时创建）"),
                             "没有写权限，换一个目录" if not writable else
                             ("空间不足 20 GB，500 张约 750 MB，请清理或换盘" if free < 20 else "")))
    except OSError as e:
        checks.append(_check("data", "数据目录", "fail", f"{root}：{e}", "检查路径是否存在、盘符是否正确"))
    return checks


# ---------------------------------------------------------------- batches
def scenes_root() -> Path:
    return get_settings().data_root / "scenes"


def batch_dir(name: str) -> Path | None:
    if not scenes.BATCH_NAME.match(name):
        return None
    d = scenes_root() / name
    return d if (d / "manifest.jsonl").exists() else None


def read_manifest(d: Path) -> list[dict]:
    rows = []
    with open(d / "manifest.jsonl", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    break  # a half-written last line while the batch is still running
    return rows


def read_rejected(d: Path) -> set[str]:
    p = d / "rejected.txt"
    return set(p.read_text(encoding="utf-8").split()) if p.exists() else set()


def batch_info(d: Path, running: str | None) -> dict:
    p = d / "batch.json"
    info = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"batch": d.name}
    if info.get("status") == "running" and running != d.name:
        info["status"] = "cancelled"  # the process is gone: interrupted
    rows = read_manifest(d)
    info["images"] = len(rows)
    info["rejected"] = len(read_rejected(d) & {r["id"] for r in rows})
    info["cover"] = rows[min(len(rows) - 1, 3)]["id"] if rows else None
    info["size_mb"] = round(sum(f.stat().st_size for f in (d / "images").glob("*.png")) / 1e6, 1)
    info.setdefault("finished", time.strftime("%Y-%m-%d %H:%M:%S",
                                              time.localtime((d / "manifest.jsonl").stat().st_mtime)))
    return info


def list_batches(running: str | None) -> list[dict]:
    root = scenes_root()
    if not root.exists():
        return []
    out = [batch_info(d, running) for d in root.iterdir() if d.is_dir() and (d / "manifest.jsonl").exists()]
    return sorted(out, key=lambda b: b.get("started") or b.get("finished") or "", reverse=True)


def next_batch_name() -> str:
    root = scenes_root()
    used = {d.name for d in root.iterdir()} if root.exists() else set()
    nums = [int(m.group(1)) for n in used if (m := re.match(r"^batch(\d+)$", n))]
    k = max(nums, default=0) + 1
    while f"batch{k:02d}" in used:
        k += 1
    return f"batch{k:02d}"


def rate_estimate(batches: list[dict]) -> dict:
    """Seconds and MB per image from the latest finished batch on this machine (no guesses).
    Tiny batches are skipped: model loading dominates them."""
    done = [b for b in batches if b.get("status") == "done" and b.get("seconds") and b.get("images")]
    for b in [b for b in done if b["images"] >= 10] or done:
            return {"sec_per_image": round(b["seconds"] / b["images"], 1),
                    "mb_per_image": round(b["size_mb"] / b["images"], 2), "from": b["batch"]}
    return {}


def thumb_path(d: Path, rid: str) -> Path:
    t = d / ".thumbs" / f"{rid}.jpg"
    if not t.exists():
        import cv2

        img = imread(d / "images" / f"{rid}.png")
        h, w = img.shape[:2]
        sc = THUMB / max(h, w)
        t.parent.mkdir(exist_ok=True)
        imwrite(t, cv2.resize(img, (int(w * sc), int(h * sc)), interpolation=cv2.INTER_AREA))
    return t


LABEL_README = """SynthGuard 场景图 · 标注包 {batch}

这些图片由 AI 文生图生成，没有任何标注框，需要人工标注。

1. 类别：classes.txt，一行一个，行号（从 0 开始）就是 YOLO 的类别编号，请不要改顺序。
{classes}
2. 以画面为准：manifest.jsonl 里的 requested_classes 只是生成时提示词要求的内容，
   模型不一定照做（例如要求"没戴安全帽"却画了安全帽）。看得见才标，看不见不标。
3. 看不清是什么的部件（AI 画出的设备结构可能不合理）宁可不标。
4. 远处很小的目标请按组里统一的最小尺寸规则处理。
5. 已在网页里标为"不合格"的 {rejected} 张没有放进这个包。

生成信息：{n} 张，模型 {model}，生成时间 {when}。
"""


# ---------------------------------------------------------------- job
class Job:
    def __init__(self, params: dict):
        self.params = params
        self.batch = params["batch"]
        self.done = 0
        self.total = params["n"]
        self.errors = 0
        self.recent: collections.deque[str] = collections.deque(maxlen=8)
        self.log: collections.deque[str] = collections.deque(maxlen=200)
        self.started = time.time()
        self.first_at: float | None = None  # first image includes model loading
        self.finished: float | None = None
        self.status = "running"
        self.cancelled = False
        self.proc: subprocess.Popen | None = None

    def view(self) -> dict:
        now = self.finished or time.time()
        el = now - self.started
        if self.done >= 2 and self.first_at:
            rate = (now - self.first_at) / (self.done - 1)
        else:
            rate = el / self.done if self.done else None
        return {"batch": self.batch, "operator": self.params.get("operator", ""), "done": self.done,
                "total": self.total, "errors": self.errors, "recent": list(self.recent),
                "status": self.status, "elapsed": round(el),
                "eta": round(rate * (self.total - self.done)) if rate and self.status == "running" else None,
                "log": list(self.log)[-40:]}


class App:
    def __init__(self, allow_remote_config: bool, allow_hosts: list[str] | None = None):
        self.allow_remote_config = allow_remote_config
        # host names browsers may use for this server (IP addresses are always accepted)
        self.allowed_hosts = {"localhost", socket.gethostname().lower(), socket.getfqdn().lower()}
        self.allowed_hosts |= {h.strip().lower() for h in allow_hosts or [] if h.strip()}
        self.lock = threading.Lock()
        self.job: Job | None = None

    def running_batch(self) -> str | None:
        return self.job.batch if self.job and self.job.status == "running" else None

    def start(self, p: dict) -> Job:
        with self.lock:
            if self.running_batch():
                raise RuntimeError(f"{self.job.params.get('operator') or '有人'} 正在生成 {self.job.batch}，请等它结束")
            cmd = [sys.executable, "-u", "-m", "synthguard", "scenes", "--spec", p["spec"],
                   "--n", str(p["n"]), "--batch", p["batch"], "--seed", str(p["seed"]),
                   "--operator", p.get("operator", "")]
            if p.get("weights"):
                cmd += ["--weights", ",".join(f"{k}={v}" for k, v in p["weights"].items())]
            job = Job(p)
            env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
            job.proc = subprocess.Popen(cmd, cwd=repo_root(), env=env, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                        errors="replace")
            self.job = job
        threading.Thread(target=self._pump, args=(job,), daemon=True).start()
        return job

    def _pump(self, job: Job) -> None:
        for line in job.proc.stdout:
            line = line.rstrip()
            job.log.append(line)
            if m := PROGRESS.match(line):
                job.done = int(m.group(1))
                job.first_at = job.first_at or time.time()
                job.recent.append(m.group(3))
            elif ERROR.match(line):
                job.errors += 1
        rc = job.proc.wait()
        job.finished = time.time()
        job.status = "cancelled" if job.cancelled else ("done" if rc == 0 else "failed")
        d = scenes_root() / job.batch
        info_p = d / "batch.json"
        if job.status != "done" and info_p.exists():
            info = json.loads(info_p.read_text(encoding="utf-8"))
            if info.get("status") == "running":
                info.update(status=job.status, images=job.done, finished=time.strftime("%Y-%m-%d %H:%M:%S"),
                            seconds=round(job.finished - job.started, 1))
                info_p.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

    def cancel(self) -> None:
        job = self.job
        if not job or job.status != "running":
            return
        job.cancelled = True
        job.proc.terminate()
        url = get_settings().comfy_url.rstrip("/")
        for path, body in (("/queue", {"clear": True}), ("/interrupt", {})):
            try:
                requests.post(url + path, json=body, timeout=5)
            except requests.RequestException:
                pass
        gc.free_vram(url)


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    app: App
    server_version = "SynthGuardUI"

    def log_message(self, fmt, *args):  # quiet: only errors
        pass

    # helpers
    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _err(self, msg, status=400):
        self._json({"error": msg}, status)

    def _file(self, path: Path, ctype=None, cache=False):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype or mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=86400" if cache else "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > 1_000_000:
            raise ValueError("request too large")
        return json.loads(self.rfile.read(n) or b"{}")

    def _local(self) -> bool:
        return self.client_address[0] in ("127.0.0.1", "::1", "::ffff:127.0.0.1")

    def _host_ok(self) -> bool:
        """Block DNS rebinding (a foreign domain pointed at this machine). IP literals and
        this machine's own names cannot be rebound, so they are always fine."""
        host = (self.headers.get("Host") or "").strip().lower()
        name = host[1:host.find("]")] if host.startswith("[") else host.rsplit(":", 1)[0]
        if not name:
            return False
        try:
            ipaddress.ip_address(name)
            return True
        except ValueError:
            return name in self.app.allowed_hosts

    def _same_origin_json(self) -> bool:
        """A cross-site page can POST text/plain without a CORS preflight. Requiring JSON
        forces a preflight (never granted here), and a present Origin must be this server."""
        if not (self.headers.get("Content-Type") or "").lower().startswith("application/json"):
            return False
        origin = self.headers.get("Origin")
        return origin is None or urlparse(origin).netloc.lower() == (self.headers.get("Host") or "").lower()

    def _can_config(self) -> bool:
        return self._local() or self.app.allow_remote_config

    # routes
    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if not self._host_ok():
            return self._err(HOST_REFUSED, 403)
        try:
            if path in ("/", "/index.html"):
                return self._file(STATIC / "index.html", "text/html; charset=utf-8")
            if path.startswith("/static/"):
                f = (STATIC / path[len("/static/"):]).resolve()
                if not f.is_relative_to(STATIC.resolve()) or not f.is_file():
                    return self._err("not found", 404)
                # hashed build assets never change under the same name
                return self._file(f, cache=f.parent.name == "assets")
            if path == "/api/state":
                return self._json(self._state())
            if path == "/api/health":
                return self._json({"checks": health(), "gpus": gpus()})
            if path == "/api/config":
                return self._json(self._config())
            if path == "/api/config/export":
                data = env_path().read_bytes() if env_path().exists() else b""
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="{socket.gethostname()}.env"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                return self.wfile.write(data)
            if path == "/api/specs":
                return self._json(self._specs())
            if path == "/api/batches":
                return self._json({"batches": list_batches(self.app.running_batch())})
            m = re.match(r"^/api/batches/([^/]+)(?:/(thumb|image)/([^/]+)|/(download))?$", path)
            if m:
                d = batch_dir(m.group(1))
                if d is None:
                    return self._err("没有这个批次", 404)
                if m.group(4):
                    return self._download(d)
                if m.group(2):
                    rid = m.group(3)
                    if not re.match(r"^[A-Za-z0-9_-]+$", rid) or not (d / "images" / f"{rid}.png").exists():
                        return self._err("没有这张图", 404)
                    if m.group(2) == "thumb":
                        return self._file(thumb_path(d, rid), "image/jpeg", cache=True)
                    return self._file(d / "images" / f"{rid}.png", "image/png", cache=True)
                rows = read_manifest(d)
                return self._json({"info": batch_info(d, self.app.running_batch()), "rows": rows,
                                   "rejected": sorted(read_rejected(d))})
            return self._err("not found", 404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # keep the server alive; show the reason in the page
            self._err(f"{type(e).__name__}: {e}", 500)

    def do_POST(self):
        path = urlparse(self.path).path
        if not self._host_ok():
            return self._err(HOST_REFUSED, 403)
        if not self._same_origin_json():
            return self._err("跨站请求被拒绝：只接受本页面发出的 JSON 请求", 403)
        try:
            body = self._body()
            if not isinstance(body, dict):
                raise ValueError("请求内容要是 JSON 对象")
            if path == "/api/preview":
                spec = scenes.with_weights(load_yaml(f"scenes_{spec_name(body.get('spec'))}"), body.get("weights"))
                n = max(1, min(int(body.get("n", 50)), 5000))
                return self._json({"coverage": scenes.preview(spec, n, int(body.get("seed", 0))), "n": n})
            if path == "/api/jobs":
                return self._start(body)
            if path == "/api/jobs/cancel":
                self.app.cancel()
                return self._json({"ok": True})
            if path == "/api/config":
                if not self._can_config():
                    return self._err("只有在这台机器上打开的页面才能修改配置", 403)
                vals = {k: str(body.get(k, "")).strip() for k in ENV_KEYS}
                errs = validate_env(vals)
                if errs:
                    return self._json({"errors": errs}, 400)
                write_env(vals)
                return self._json({"ok": True})
            m = re.match(r"^/api/batches/([^/]+)/reject$", path)
            if m:
                d = batch_dir(m.group(1))
                if d is None:
                    return self._err("没有这个批次", 404)
                ids = {r["id"] for r in read_manifest(d)}
                rej = read_rejected(d)
                for rid in body.get("ids", []):
                    if rid in ids:
                        (rej.add if body.get("rejected", True) else rej.discard)(rid)
                (d / "rejected.txt").write_text("\n".join(sorted(rej)) + ("\n" if rej else ""),
                                                encoding="utf-8", newline="\n")
                return self._json({"rejected": sorted(rej)})
            return self._err("not found", 404)
        except (ValueError, KeyError) as e:
            self._err(f"参数不对：{e}")
        except Exception as e:
            self._err(f"{type(e).__name__}: {e}", 500)

    # route bodies
    def _state(self) -> dict:
        s = get_settings()
        st = gc.probe(s.comfy_url, timeout=1.5)
        job = self.app.job
        return {"host": socket.gethostname(), "comfy_url": s.comfy_url, "comfy_online": st is not None,
                "comfy_devices": [d.get("name", "") for d in (st or {}).get("devices", [])],
                "gen_profile": s.gen_profile, "can_config": self._can_config(),
                "job": job.view() if job else None}

    def _config(self) -> dict:
        file_vals = read_env()
        fields = []
        for key, label, group, help_ in ENV_FIELDS:
            f = Settings.model_fields.get(key.lower())
            dflt = f.default if f else ""
            dflt = ("1" if dflt else "0") if isinstance(dflt, bool) else str(dflt)
            fields.append({"key": key, "label": label, "group": group, "help": help_,
                           "value": file_vals.get(key, dflt), "in_file": key in file_vals,
                           "overridden": key in os.environ})
        weights = {}
        try:
            weights = load_yaml(f"gen_{get_settings().gen_profile}")["weights"].get("krea2") or {}
        except FileNotFoundError:
            pass
        return {"fields": fields, "profiles": gen_profiles(), "exists": env_path().exists(),
                "can_config": self._can_config(), "repo": str(repo_root()), "krea2": weights}

    def _specs(self) -> dict:
        out = []
        for p in sorted((repo_root() / "configs").glob("scenes_*.yaml")):
            sp = load_yaml(p)
            out.append({"name": sp["name"], "title": sp.get("title", sp["name"]),
                        "description": sp.get("description", ""), "classes": sp["classes"],
                        "class_labels": sp.get("class_labels", {}),
                        "elements": [{"name": k, "label": sp.get("element_labels", {}).get(k, k),
                                      "shows": v["shows"], "weight": sp["weights"].get(k, 1)}
                                     for k, v in sp["elements"].items()]})
        batches = list_batches(self.app.running_batch())
        return {"specs": out, "next_batch": next_batch_name(), "rate": rate_estimate(batches)}

    def _start(self, b: dict):
        spec = spec_name(b.get("spec"))
        if not (repo_root() / "configs" / f"scenes_{spec}.yaml").exists():
            return self._err("没有这个场景")
        batch = str(b.get("batch", "")).strip()
        if not scenes.BATCH_NAME.match(batch):
            return self._err("批次名只能用字母、数字、- 和 _，最多 40 个字符")
        if (scenes_root() / batch).exists():
            return self._err(f"批次 {batch} 已经存在，换一个名字（已有的图不会被覆盖）")
        n = int(b.get("n", 0))
        if not 1 <= n <= 5000:
            return self._err("数量要在 1 到 5000 之间")
        spec_y = load_yaml(f"scenes_{spec}")
        # keep only real changes, so batch.json records what differed from the spec
        weights = {k: float(v) for k, v in (b.get("weights") or {}).items()
                   if float(v) != spec_y["weights"].get(k, 1)}
        scenes.with_weights(spec_y, weights)  # raises on unknown element names
        if not gc.probe(get_settings().comfy_url):
            return self._err("ComfyUI 没有连上，先到「环境」页检查")
        operator = re.sub(r"[\r\n,]", " ", str(b.get("operator", "")))[:40].strip()
        try:
            job = self.app.start({"spec": spec, "n": n, "batch": batch, "seed": int(b.get("seed", 0)),
                                  "operator": operator, "weights": weights})
        except RuntimeError as e:
            return self._err(str(e), 409)
        return self._json({"job": job.view()})

    def _download(self, d: Path):
        rows = read_manifest(d)
        rej = read_rejected(d)
        keep = [r for r in rows if r["id"] not in rej]
        info = batch_info(d, self.app.running_batch())
        classes = (d / "classes.txt").read_text(encoding="utf-8").split()
        labels = {}
        try:
            labels = load_yaml(f"scenes_{info.get('spec', 'substation')}").get("class_labels", {})
        except FileNotFoundError:
            pass
        readme = LABEL_README.format(
            batch=d.name, rejected=len(rows) - len(keep), n=len(keep), model=info.get("model", "?"),
            when=info.get("finished", "?"),
            classes="\n".join(f"   {i}  {c}  {labels.get(c, '')}" for i, c in enumerate(classes)))
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f'attachment; filename="{d.name}_labeling.zip"')
        self.end_headers()  # HTTP/1.0: no length, the connection close ends the body
        with zipfile.ZipFile(self.wfile, "w", zipfile.ZIP_STORED) as z:
            z.writestr(f"{d.name}/README_标注说明.txt", readme)
            z.write(d / "classes.txt", f"{d.name}/classes.txt")
            z.writestr(f"{d.name}/manifest.jsonl",
                       "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep))
            root = d.resolve()
            for r in keep:
                f = (d / r["file"]).resolve()
                if f.is_relative_to(root) and f.is_file():  # a hand-edited manifest cannot reach outside
                    z.write(f, f"{d.name}/{r['file']}")


def serve(host: str = "127.0.0.1", port: int = 8765, allow_remote_config: bool = False,
          open_browser: bool = False, allow_hosts: list[str] | None = None) -> None:
    Handler.app = App(allow_remote_config, allow_hosts)
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    url = f"http://127.0.0.1:{port}/"
    print(f"SynthGuard UI: {url}")
    if host not in ("127.0.0.1", "localhost"):
        print(f"  同事访问：http://{socket.gethostname()}:{port}/ （修改配置仅限本机"
              f"{'，已放开' if allow_remote_config else ''}）")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if Handler.app.job and Handler.app.job.status == "running":
            Handler.app.cancel()
