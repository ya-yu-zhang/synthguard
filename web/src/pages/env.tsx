import { useRef, useState } from "react"
import { Check, CircleCheck, Copy, Info, Loader2, Minus, Plus, TriangleAlert, X, type LucideIcon } from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { useApp } from "@/app-context"
import { useResource } from "@/hooks/use-resource"
import { api, ApiError, type CheckStatus, type Config, type ConfigField, type Health } from "@/lib/api"
import { href } from "@/lib/route"
import { copyText } from "@/lib/store"
import { ArrowLink, LocalNav, Ribbon } from "@/components/bits"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"

const jump = (id: string) => (e: React.MouseEvent) => {
  e.preventDefault() // hash routing: don't let #id replace the page route
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth" })
}

export function EnvPage() {
  const { refresh, state } = useApp()
  const [round, setRound] = useState(0)
  const health = useResource<Health>("/api/health", round)
  const config = useResource<Config>("/api/config", round)
  const recheck = () => {
    setRound((r) => r + 1)
    void refresh()
  }
  const busy = health.loading || (!health.data && !health.error)
  const bad = health.data?.checks.filter((c) => c.status === "fail").length ?? 0
  const ok = !busy && !health.error && bad === 0

  return (
    <>
      <LocalNav title="环境与迁移">
        <a href="#settings" onClick={jump("settings")} className="hidden text-foreground/75 hover:text-foreground sm:inline">
          配置
        </a>
        <a href="#migrate" onClick={jump("migrate")} className="hidden text-foreground/75 hover:text-foreground sm:inline">
          迁移
        </a>
        <Button size="sm" onClick={recheck} disabled={busy}>
          重新检查
        </Button>
      </LocalNav>

      <section className="px-4 pt-16 pb-14 text-center sm:pt-24">
        <div
          className={cn(
            "mx-auto grid size-16 place-items-center rounded-full",
            busy ? "bg-alt text-faint" : ok ? "bg-success-soft text-success" : "bg-danger-soft text-destructive",
          )}
        >
          {busy ? (
            <Loader2 className="size-7 animate-spin" />
          ) : ok ? (
            <CircleCheck className="size-8" strokeWidth={1.8} />
          ) : (
            <TriangleAlert className="size-8" strokeWidth={1.8} />
          )}
        </div>
        <h1 className="type-hero mt-6">
          {busy ? "正在检查。" : health.error ? "检查失败。" : ok ? "这台机器，可以生图。" : `还有 ${bad} 项，要处理。`}
        </h1>
        <p className="type-sub mx-auto mt-4 max-w-[34em] text-muted-foreground">
          {health.error || `${state?.host ?? "这台机器"}：显卡、ComfyUI、模型文件、磁盘空间，逐项检查。`}
        </p>
      </section>

      <Specs health={health.data} />
      <Settings config={config.data} error={config.error} onSaved={recheck} />
      <Migration health={health.data} config={config.data} />
    </>
  )
}

/* ------------------------------------------------------------------ specs */

const CHECK_ICON: Record<CheckStatus, LucideIcon> = { ok: Check, warn: TriangleAlert, fail: X, skip: Info }

function Specs({ health }: { health: Health | null }) {
  return (
    <section className="mx-auto max-w-[980px] px-4 pb-20 sm:px-6">
      <h2 className="type-headline border-b border-border pb-5">体检</h2>
      <dl>
        {!health &&
          Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="border-b border-hairline py-6">
              <Skeleton className="h-5 w-2/3" />
            </div>
          ))}
        {health?.checks.map((c) => {
          const Icon = CHECK_ICON[c.status]
          return (
            <div key={c.id} className="grid gap-x-8 gap-y-1 border-b border-hairline py-6 sm:grid-cols-[220px_minmax(0,1fr)]">
              <dt className="flex items-center gap-2.5 text-[17px] font-semibold tracking-[-0.02em]">
                <span
                  className={cn(
                    "grid size-5 place-items-center rounded-full",
                    c.status === "ok" && "bg-success text-white",
                    c.status === "warn" && "bg-orange text-white",
                    c.status === "fail" && "bg-destructive text-white",
                    c.status === "skip" && "bg-faint/30 text-muted-foreground",
                  )}
                >
                  <Icon className="size-3" strokeWidth={3} />
                </span>
                {c.label}
              </dt>
              <dd className="min-w-0 pl-[30px] sm:pl-0">
                <div className="break-all text-[17px] text-foreground/85">{c.detail}</div>
                {c.fix && <div className="mt-1 text-sm text-orange">{c.fix}</div>}
              </dd>
            </div>
          )
        })}
      </dl>
    </section>
  )
}

/* ------------------------------------------------------------------ settings */

function SettingsForm({ config, onSaved }: { config: Config; onSaved: () => void }) {
  const [values, setValues] = useState<Record<string, string> | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [more, setMore] = useState(false)
  const file = useRef<HTMLInputElement>(null)
  const vals = values ?? Object.fromEntries(config.fields.map((f) => [f.key, f.value]))
  const ro = !config.can_config
  const set = (k: string, v: string) => setValues({ ...vals, [k]: v })

  async function save() {
    setSaving(true)
    setErrors([])
    try {
      await api("/api/config", vals)
      toast.success("已保存", { description: "正在重新检查这台机器" })
      setValues(null)
      onSaved()
    } catch (e) {
      setErrors(e instanceof ApiError && e.errors.length ? e.errors : [(e as Error).message])
    } finally {
      setSaving(false)
    }
  }

  async function importEnv(f: File) {
    const text = await f.text()
    const next = { ...vals }
    let n = 0
    for (const line of text.split(/\r?\n/)) {
      const m = line.match(/^\s*([A-Z_]+)\s*=\s*(.*?)\s*$/)
      if (!m || line.trim().startsWith("#") || !(m[1] in next)) continue
      next[m[1]] = m[2].replace(/^["']|["']$/g, "")
      n++
    }
    setValues(next)
    if (n) toast(`已填入 ${n} 项`, { description: "路径通常每台机器都不一样，检查后再保存" })
    else toast.error("这个文件里没有认识的配置项")
  }

  const row = (f: ConfigField) => (
    <div key={f.key} className="grid gap-3 px-5 py-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)] sm:items-center sm:gap-6">
      <label htmlFor={`c-${f.key}`} className="min-w-0">
        <div className="text-[17px] tracking-[-0.02em]">{f.label}</div>
        <div className="mt-0.5 text-xs text-muted-foreground">{f.help}</div>
        {f.overridden && <div className="mt-1 text-xs text-orange">被系统环境变量覆盖了，改这里不会生效。</div>}
      </label>
      {f.key === "GEN_PROFILE" || f.key === "SKIP_DIFFUSION" ? (
        <Select value={vals[f.key] === "true" ? "1" : vals[f.key]} onValueChange={(v) => set(f.key, v)} disabled={ro}>
          <SelectTrigger id={`c-${f.key}`} className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {f.key === "GEN_PROFILE"
              ? config.profiles.map((p) => (
                  <SelectItem key={p} value={p} className="font-mono">
                    {p}
                  </SelectItem>
                ))
              : [
                  <SelectItem key="0" value="0">
                    不跳过
                  </SelectItem>,
                  <SelectItem key="1" value="1">
                    跳过
                  </SelectItem>,
                ]}
          </SelectContent>
        </Select>
      ) : (
        <input
          id={`c-${f.key}`}
          value={vals[f.key] ?? ""}
          disabled={ro}
          spellCheck={false}
          autoComplete="off"
          onChange={(e) => set(f.key, e.target.value)}
          className="h-12 w-full min-w-0 rounded-xl border border-input/70 bg-background px-4 font-mono text-[15px] outline-none transition-[border-color,box-shadow] focus:border-primary focus:ring-4 focus:ring-primary/20 disabled:bg-alt disabled:text-muted-foreground"
        />
      )}
    </div>
  )

  return (
    <>
      {ro && (
        <p className="mb-4 rounded-2xl bg-tile px-5 py-4 text-sm text-muted-foreground">
          你是从其他电脑打开的页面，只能查看。要修改，请在生图机器上打开{" "}
          <span className="font-mono text-foreground">http://127.0.0.1:8765</span>。
        </p>
      )}
      {!config.exists && (
        <p className="mb-4 rounded-2xl bg-warning-soft px-5 py-4 text-sm">这台机器还没有 .env。下面是默认值，检查后点「保存」就会生成。</p>
      )}
      {errors.length > 0 && (
        <div role="alert" className="mb-4 rounded-2xl bg-danger-soft px-5 py-4 text-sm text-destructive">
          {errors.map((e) => (
            <div key={e}>{e}</div>
          ))}
        </div>
      )}

      <div className="px-1 text-xs font-semibold text-muted-foreground">生图</div>
      <div className="mt-2 divide-y divide-hairline overflow-hidden rounded-[18px] bg-tile">
        {config.fields.filter((f) => f.group === "gen").map(row)}
      </div>

      <button
        type="button"
        onClick={() => setMore((m) => !m)}
        aria-expanded={more}
        className="mt-8 inline-flex items-center gap-2 text-[15px] text-link hover:underline underline-offset-4"
      >
        <span className="grid size-5 place-items-center rounded-full border border-current">
          {more ? <Minus className="size-3" /> : <Plus className="size-3" />}
        </span>
        检测实验相关（只生图不用改）
      </button>
      {more && (
        <div className="mt-3 divide-y divide-hairline overflow-hidden rounded-[18px] bg-tile animate-in fade-in">
          {config.fields.filter((f) => f.group !== "gen").map(row)}
        </div>
      )}

      <div className="mt-10 flex flex-wrap items-center gap-x-8 gap-y-4">
        {!ro && (
          <Button size="lg" onClick={save} disabled={saving}>
            {saving && <Loader2 className="animate-spin" />}
            {values ? "保存修改" : "保存"}
          </Button>
        )}
        {!ro && <ArrowLink onClick={() => file.current?.click()}>从文件导入</ArrowLink>}
        {config.exists && (
          <ArrowLink href="/api/config/export" download>
            导出 .env
          </ArrowLink>
        )}
        {values && !ro && <span className="text-sm text-orange">有未保存的修改</span>}
        <input
          ref={file}
          type="file"
          accept=".env,.txt,text/plain"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) void importEnv(f)
            e.target.value = ""
          }}
        />
      </div>
    </>
  )
}

function Settings({ config, error, onSaved }: { config: Config | null; error: string | null; onSaved: () => void }) {
  return (
    <section id="settings" className="scroll-mt-28 bg-alt">
      <div className="mx-auto max-w-[980px] px-4 py-20 sm:px-6">
        <h2 className="type-headline">
          本机配置。<span className="text-muted-foreground">写在 .env 里，每台机器一份。</span>
        </h2>
        <div className="mt-10">
          {error ? (
            <Ribbon tone="bad">读不到配置：{error}</Ribbon>
          ) : config ? (
            <SettingsForm config={config} onSaved={onSaved} />
          ) : (
            <Skeleton className="h-80 w-full rounded-[18px]" />
          )}
        </div>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ migration */

function CodeLine({ text }: { text: string }) {
  return (
    <div className="mt-3 flex items-stretch overflow-hidden rounded-xl bg-alt">
      <code className="flex-1 px-4 py-3 font-mono text-[13px] leading-relaxed break-all whitespace-pre-wrap">{text}</code>
      <button
        onClick={async () => {
          await copyText(text)
          toast("已复制命令")
        }}
        className="grid w-11 shrink-0 place-items-center text-muted-foreground transition-colors hover:text-link"
        aria-label="复制命令"
        title="复制"
      >
        <Copy className="size-4" />
      </button>
    </div>
  )
}

function Migration({ health, config }: { health: Health | null; config: Config | null }) {
  const st = Object.fromEntries((health?.checks ?? []).map((c) => [c.id, c.status]))
  const k = config?.krea2 ?? {}
  const repo = config?.repo ?? "<仓库目录>"
  const allOk = !!health && health.checks.every((c) => c.status !== "fail")
  const steps: { done: boolean; title: string; desc?: React.ReactNode; body?: React.ReactNode }[] = [
    {
      done: false,
      title: "复制代码。",
      desc: "不要复制 .venv、data 和 .env：环境要重建，配置每台机器不同。",
      body: <CodeLine text={`robocopy "${repo}" "<目标目录>\\synthguard" /E /XD .venv data node_modules .pytest_cache __pycache__ /XF .env`} />,
    },
    {
      done: st.python === "ok",
      title: "建 Python 环境。",
      desc: "需要 Python 3.12 和 uv，在新机器的仓库目录里依次运行。不需要 Node，界面已经打包好。",
      body: (
        <>
          <CodeLine text="uv venv .venv --python 3.12" />
          <CodeLine text="uv pip install -p .venv -r requirements.lock.txt --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match" />
          <CodeLine text="uv pip install -p .venv -e . --no-deps" />
        </>
      ),
    },
    {
      done: st.weights === "ok",
      title: "放模型文件。",
      desc: "复制到新机器 ComfyUI 的 models 目录下。3090 不支持 nvfp4 硬件加速，如果报错或很慢，换成 fp8 版本，再到 configs/gen_deploy_3090.yaml 改文件名。",
      body: (
        <ul className="mt-3 space-y-1.5 rounded-xl bg-alt px-4 py-3 font-mono text-[13px] break-all">
          {k.unet && <li>diffusion_models/{k.unet}</li>}
          {k.text_encoder && <li>clip/{k.text_encoder}</li>}
          {k.vae && <li>vae/{k.vae}</li>}
        </ul>
      ),
    },
    {
      done: st.comfy === "ok",
      title: "启动 ComfyUI。",
      desc: "双卡机器让 ComfyUI 用第 1 张卡，第 2 张留给训练。",
      body: <CodeLine text="set CUDA_VISIBLE_DEVICES=0 && python main.py --listen 127.0.0.1 --port 8188" />,
    },
    {
      done: true,
      title: "打开这个页面。",
      desc: "双击 scripts\\start_ui.bat。想让同事从自己的电脑打开，改用：",
      body: <CodeLine text=".venv\Scripts\python -m synthguard ui --host 0.0.0.0 --open" />,
    },
    {
      done: allOk,
      title: "填配置，体检。",
      desc: "在上面的本机配置里填好并保存，体检全部通过就可以生图。也可以先在旧机器「导出 .env」，到新机器「从文件导入」再改路径。",
    },
    {
      done: false,
      title: "先试 20 张。",
      desc: "确认画面和速度都正常，再批量生成。",
      body: (
        <div className="mt-3">
          <ArrowLink href={href("generate")}>去生成</ArrowLink>
        </div>
      ),
    },
    {
      done: false,
      title: "带走已生成的图（可选）。",
      desc: "把旧机器的 数据目录\\scenes 整个文件夹复制到新机器的数据目录下，结果页就能看到。",
    },
  ]
  return (
    <section id="migrate" className="mx-auto max-w-[980px] scroll-mt-28 px-4 py-20 sm:px-6 sm:py-28">
      <h2 className="type-headline">
        迁移到新机器。<span className="text-muted-foreground">照着做，八步。</span>
      </h2>
      <p className="mt-4 text-[17px] text-muted-foreground">
        打勾的步骤，这台机器已经验证通过。完整说明见 <span className="font-mono text-foreground">docs/deploy_3090.md</span>。
      </p>
      <ol className="mt-12 grid gap-x-12 gap-y-12 md:grid-cols-2">
        {steps.map((s, i) => (
          <li key={s.title} className="min-w-0">
            <div className="flex items-center gap-3">
              {s.done ? (
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-success text-white">
                  <Check className="size-4" strokeWidth={3} />
                </span>
              ) : (
                <span className="w-9 shrink-0 text-center text-[40px] leading-none font-semibold tracking-[-0.04em] text-faint/60 tabular">
                  {i + 1}
                </span>
              )}
              <h3 className="text-[21px] font-semibold tracking-[-0.02em]">{s.title}</h3>
            </div>
            {s.desc && <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">{s.desc}</p>}
            {s.body}
          </li>
        ))}
      </ol>
    </section>
  )
}
