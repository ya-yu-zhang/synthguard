import io
import json
import re
import threading
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer

import numpy as np
import pytest

from synthguard import scenes, ui_server
from synthguard.records import imwrite, load_yaml


def _make_batch(root, name="b1", n=3):
    d = root / "data" / "scenes" / name
    (d / "images").mkdir(parents=True)
    (d / "classes.txt").write_text("person\nhelmet\n", encoding="utf-8")
    rows = []
    for k in range(n):
        rid = f"substation_{name}_{k:04d}"
        imwrite(d / "images" / f"{rid}.png", np.full((64, 96, 3), 40 * k, np.uint8))
        rows.append({"id": rid, "file": f"images/{rid}.png", "w": 96, "h": 64, "seed": k,
                     "model": "m", "steps": 8, "prompt": "p", "elements": ["fence"],
                     "requested_classes": ["safety_fence"]})
    (d / "manifest.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    (d / "batch.json").write_text(json.dumps({"batch": name, "spec": "substation", "status": "done",
                                              "seconds": 30.0, "images": n}), encoding="utf-8")
    return d, rows


@pytest.fixture
def server(isolated_data, monkeypatch, tmp_path):
    monkeypatch.setenv("COMFY_URL", "http://127.0.0.1:9")  # nothing listens: Comfy offline
    monkeypatch.setattr(ui_server, "env_path", lambda: tmp_path / "test.env")
    ui_server.Handler.app = ui_server.App(allow_remote_config=False)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ui_server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.read()


def _post(url, body):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _status(url, method="GET", headers=None, data=None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def test_cross_site_posts_are_refused(server):
    url = server + "/api/jobs/cancel"
    host = server.split("//", 1)[1]
    # text/plain needs no CORS preflight, so any web page could send it: refused
    assert _status(url, "POST", {"Content-Type": "text/plain"}, b"{}") == 403
    assert _status(url, "POST", {"Content-Type": "application/json", "Origin": "http://evil.example"}, b"{}") == 403
    assert _status(url, "POST", {"Content-Type": "application/json", "Origin": f"http://{host}"}, b"{}") == 200


def test_foreign_host_names_are_refused(server):
    port = server.rsplit(":", 1)[1]
    assert _status(server + "/api/config", headers={"Host": f"attacker.example:{port}"}) == 403  # DNS rebinding
    assert _status(server + "/api/config", headers={"Host": f"localhost:{port}"}) == 200
    assert _status(server + "/api/config", headers={"Host": f"10.1.2.3:{port}"}) == 200  # IPs cannot be rebound


def test_bad_spec_and_weights_are_rejected(server):
    status, _ = _post(server + "/api/preview", {"spec": "../../configs/mvp", "n": 5})
    assert status == 400
    status, _ = _post(server + "/api/preview", {"spec": "substation", "n": 5, "weights": {"robot_arm": "nan"}})
    assert status == 400


def test_write_env_keeps_comments_and_unknown_keys(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text("# my note\nCOMFY_URL=http://old:1\nOTHER=x\n", encoding="utf-8")
    monkeypatch.setattr(ui_server, "env_path", lambda: p)
    ui_server.write_env({"COMFY_URL": "http://127.0.0.1:8188", "GEN_PROFILE": "deploy_3090"})
    assert p.read_text(encoding="utf-8").splitlines() == [
        "# my note", "COMFY_URL=http://127.0.0.1:8188", "OTHER=x", "GEN_PROFILE=deploy_3090"]


def test_validate_env_rejects_bad_values():
    ok = {"COMFY_URL": "http://127.0.0.1:8188", "GEN_PROFILE": "dev_5070",
          "SYNTHGUARD_DATA_ROOT": "./data", "SKIP_DIFFUSION": "0"}
    assert ui_server.validate_env(ok) == []
    assert len(ui_server.validate_env({**ok, "COMFY_URL": "127.0.0.1", "GEN_PROFILE": "nope",
                                       "SKIP_DIFFUSION": "yes"})) == 3


def test_preview_and_weight_override():
    spec = load_yaml("scenes_substation")
    base = scenes.preview(spec, 200, seed=1)
    more = scenes.preview(scenes.with_weights(spec, {"robot_arm": 6}), 200, seed=1)
    assert more["mechanical_arm"] > base["mechanical_arm"]
    with pytest.raises(ValueError):
        scenes.with_weights(spec, {"nope": 2})
    assert set(spec["class_labels"]) == set(spec["classes"])
    assert set(spec["element_labels"]) == set(spec["elements"])


def test_scenes_never_overwrites_a_batch(isolated_data):
    _make_batch(isolated_data, "b1")
    with pytest.raises(FileExistsError):
        scenes.run("substation", 1, "b1")
    with pytest.raises(ValueError):
        scenes.run("substation", 1, "../escape")


def test_batches_reject_and_labeling_zip(server, isolated_data):
    _, rows = _make_batch(isolated_data, "b1")
    listing = json.loads(_get(server + "/api/batches"))["batches"]
    assert [b["batch"] for b in listing] == ["b1"] and listing[0]["images"] == 3
    assert _get(f"{server}/api/batches/b1/thumb/{rows[0]['id']}")[:2] == b"\xff\xd8"  # jpeg
    status, res = _post(f"{server}/api/batches/b1/reject", {"ids": [rows[1]["id"], "unknown"]})
    assert status == 200 and res["rejected"] == [rows[1]["id"]]
    z = zipfile.ZipFile(io.BytesIO(_get(f"{server}/api/batches/b1/download")))
    pngs = sorted(n for n in z.namelist() if n.endswith(".png"))
    assert pngs == [f"b1/images/{rows[0]['id']}.png", f"b1/images/{rows[2]['id']}.png"]
    assert "b1/README_标注说明.txt" in z.namelist()
    assert len(z.read("b1/manifest.jsonl").decode().splitlines()) == 2


def test_paths_outside_scenes_are_refused(server, isolated_data):
    _make_batch(isolated_data, "b1")
    for path in ("/api/batches/..%2F..%2Fconfigs/download", "/api/batches/b1/image/..%2Fclasses",
                 "/static/..%2F..%2Fsettings.py"):
        with pytest.raises(urllib.error.HTTPError) as e:
            _get(server + path)
        assert e.value.code == 404


def test_serves_the_built_web_app(server):
    html = _get(server + "/").decode("utf-8")
    assert '<div id="root">' in html
    assets = re.findall(r'(?:src|href)="(/static/assets/[^"]+)"', html)
    assert any(a.endswith(".js") for a in assets) and any(a.endswith(".css") for a in assets)
    for a in assets:
        assert len(_get(server + a)) > 0  # the committed build is complete
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(server + "/static/assets/..%2F..%2Fui_server.py")
    assert e.value.code == 404


def test_start_job_guards(server, isolated_data):
    _make_batch(isolated_data, "b1")
    status, res = _post(server + "/api/jobs", {"spec": "substation", "n": 5, "batch": "b1"})
    assert status == 400 and "已经存在" in res["error"]
    status, res = _post(server + "/api/jobs", {"spec": "substation", "n": 5, "batch": "b2"})
    assert status == 400 and "ComfyUI" in res["error"]
    status, res = _post(server + "/api/jobs", {"spec": "substation", "n": 5, "batch": "a/b"})
    assert status == 400


def test_config_roundtrip_local_only(server, tmp_path):
    cfg = json.loads(_get(server + "/api/config"))
    assert cfg["can_config"] and not cfg["exists"]
    body = {f["key"]: f["value"] for f in cfg["fields"]}
    body["GEN_PROFILE"] = "deploy_3090"
    status, _ = _post(server + "/api/config", body)
    assert status == 200 and "GEN_PROFILE=deploy_3090" in (tmp_path / "test.env").read_text(encoding="utf-8")
    status, res = _post(server + "/api/config", {**body, "COMFY_URL": "nope"})
    assert status == 400 and res["errors"]
