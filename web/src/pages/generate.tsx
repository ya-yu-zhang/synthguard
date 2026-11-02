import { useEffect, useMemo, useRef, useState } from "react"
import { Dices, Loader2, Minus, Plus, TriangleAlert } from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { useApp } from "@/app-context"
import { useResource } from "@/hooks/use-resource"
import { api, thumbUrl, type BatchInfo, type Job, type Rate, type Spec, type Specs } from "@/lib/api"
import { fmtDur, fmtMB, shortId } from "@/lib/format"
import { href } from "@/lib/route"
import { store } from "@/lib/store"
import { ArrowLink, BrandGlyph, Fn, Hero, LocalNav, Ribbon, StatusDot, StepTitle } from "@/components/bits"
import { useConfirm } from "@/components/confirm"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

const COUNTS: { n: number; note?: string }[] = [{ n: 20, note: "先试试，看看画面" }, { n: 100 }, { n: 500 }, { n: 1000 }]
const FACTORS = [
  { label: "少", v: 0.4 },
  { label: "常", v: 1 },
  { label: "多", v: 2.5 },
]
const randomSeed = () => Math.floor(Math.random() * 100000)

type Form = {
  n: number
  custom: boolean
  batch: string
  seed: number
  operator: string
  tune: boolean
  factors: Record<string, number>
}
type SetForm = (f: (prev: Form | null) => Form | null) => void
type Coverage = { coverage: Record<string, number>; n: number }

function weightsFor(spec: Spec, form: Form) {
  const out: Record<string, number> = {}
  if (!form.tune) return out
  for (const e of spec.elements) {
    const f = form.factors[e.name]
    if (f && f !== 1) out[e.name] = Math.round(e.weight * f * 100) / 100
  }
  return out
}

export function GeneratePage() {
  const { state, running, finished, clearFinished, epoch, bump, refresh } = useApp()
  const specs = useResource<Specs>("/api/specs", epoch)
  const batches = useResource<{ batches: BatchInfo[] }>("/api/batches", epoch)
  const [form, setForm] = useState<Form | null>(null)
  const [starting, setStarting] = useState(false)
  const [dialog, confirm] = useConfirm()

  // fresh batch name and seed whenever the server suggests a new one (after every run)
  useEffect(() => {
    if (!specs.data) return
    const next = specs.data.next_batch
    setForm((f) => ({
      n: f?.n ?? 20,
      custom: f?.custom ?? false,
      batch: next,
      seed: randomSeed(),
      operator: f?.operator ?? store.get("operator", ""),
      tune: f?.tune ?? false,
      factors: f?.factors ?? {},
    }))
  }, [specs.data])

  const spec = specs.data?.specs[0]
  const rate = specs.data?.rate ?? {}
  const existing = useMemo(() => new Set(batches.data?.batches.map((b) => b.batch)), [batches.data])
  const last = batches.data?.batches[0]

  const problem = !form
    ? "加载中"
    : !state?.comfy_online
      ? "ComfyUI 没有连上"
      : running
        ? "已有任务在运行"
        : !(form.n >= 1 && form.n <= 5000)
          ? "数量要在 1 到 5000 之间"
          : !/^[A-Za-z0-9_-]{1,40}$/.test(form.batch)
            ? "批次名只能用字母、数字、- 和 _"
            : existing.has(form.batch)
              ? `批次 ${form.batch} 已经存在，换个名字`
              : ""

  async function start() {
    if (!form || !spec || problem) return
    const total = rate.sec_per_image ? rate.sec_per_image * form.n : 0
    if (total > 3 * 3600) {
      const ok = await confirm({
        title: `生成 ${form.n} 张？`,
        ok: "开始生成",
        body: `预计要 ${fmtDur(total)}，期间 ComfyUI 那张显卡会一直被占用。中途可以随时停止，已生成的图会保留。`,
      })
      if (!ok) return
    }
    setStarting(true)
    try {
      await api("/api/jobs", {
        spec: spec.name,
        n: form.n,
        batch: form.batch,
        seed: form.seed,
        operator: form.operator.trim(),
        weights: weightsFor(spec, form),
      })
      clearFinished()
      await refresh()
      bump()
      window.scrollTo({ top: 0, behavior: "smooth" })
    } catch (e) {
      toast.error("没有启动", { description: (e as Error).message })
    } finally {
      setStarting(false)
    }
  }

  async function stop(job: Job) {
    const ok = await confirm({
      title: `停止生成 ${job.batch}？`,
      danger: true,
      ok: "停止生成",
      cancel: "继续生成",
      body: (
        <>
          已生成的 {job.done} 张会保留，可以照常浏览和下载。
          {job.operator && (
            <>
              {" "}这个任务是 <b className="text-foreground">{job.operator}</b> 发起的，停止前最好跟 TA 说一声。
            </>
          )}
        </>
      ),
    })
    if (!ok) return
    try {
      await api("/api/jobs/cancel", {})
      toast("正在停止…")
      await refresh()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  return (
    <>
      {dialog}
      <LocalNav title="生成">
        {last && !running && (
          <a href={href("results", last.batch)} className="hidden text-foreground/75 hover:text-foreground sm:inline">
            上一批 {last.batch}
          </a>
        )}
        {running ? (
          <Button size="sm" variant="secondary" onClick={() => stop(running)}>
            停止生成
          </Button>
        ) : (
          <Button size="sm" disabled={!!problem || starting} onClick={start}>
            开始生成
          </Button>
        )}
      </LocalNav>

      {state && !state.comfy_online && (
        <Ribbon tone="warn">
          ComfyUI 没有连上，暂时不能生成。请让管理员启动它，或者 <ArrowLink href={href("env")}>检查环境</ArrowLink>
        </Ribbon>
      )}
      {finished && !running && <FinishedRibbon job={finished} onClose={clearFinished} />}

      {running ? (
        <RunningShowcase job={running} onStop={() => stop(running)} />
      ) : (
        <>
          <Hero
            eyebrow={spec?.title ?? "变电站作业场景"}
            title="生成训练图片。"
            sub="AI 生成，不带标注框。挑好图、下载，交给标注同事。"
          >
            {last && <ArrowLink href={href("results", last.batch)}>看看上一批 {last.batch}</ArrowLink>}
            <ArrowLink href={href("env")}>这台机器的状态</ArrowLink>
          </Hero>
          {form && spec ? (
            <Configurator
              spec={spec}
              form={form}
              setForm={setForm}
              rate={rate}
              last={last}
              problem={problem}
              starting={starting}
              onStart={start}
            />
          ) : (
            <div className="mx-auto grid max-w-[1024px] gap-10 px-4 pb-24 sm:px-6 lg:grid-cols-[minmax(0,1fr)_400px]">
              <Skeleton className="aspect-square w-full rounded-[28px]" />
              <div className="space-y-3">
                <Skeleton className="h-8 w-2/3" />
                <Skeleton className="h-[72px] w-full rounded-xl" />
                <Skeleton className="h-[72px] w-full rounded-xl" />
              </div>
            </div>
          )}
        </>
      )}
    </>
  )
}

/* ------------------------------------------------------------------ configurator */

function Configurator({
  spec,
  form,
  setForm,
  rate,
  last,
  problem,
  starting,
  onStart,
}: {
  spec: Spec
  form: Form
  setForm: SetForm
  rate: Rate
  last?: BatchInfo
  problem: string
  starting: boolean
  onStart: () => void
}) {
  const set = (patch: Partial<Form>) => setForm((f) => (f ? { ...f, ...patch } : f))
  const est = (n: number) => (rate.sec_per_image ? `约 ${fmtDur(rate.sec_per_image * n)}` : "")
  const preset = !form.custom && COUNTS.some((c) => c.n === form.n)
  const [more, setMore] = useState(false)
  const customRef = useRef<HTMLInputElement>(null)
  const cov = useCoverage(spec, form)
  const label = (c: string) => spec.class_labels[c] ?? c
  const low = cov && cov.n >= 30 ? spec.classes.filter((c) => (cov.coverage[c] ?? 0) < 0.08 * cov.n) : []

  return (
    <>
      <section className="mx-auto max-w-[1024px] px-4 pb-40 sm:px-6">
        <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_420px] lg:gap-16">
          <div className="lg:sticky lg:top-[120px] lg:self-start">
            <PreviewPanel spec={spec} cov={cov} last={last} low={low} />
          </div>

          <div>
            {/* 1 · count */}
            <div className="pb-12">
              <StepTitle lead="数量。" rest="这一批要多少张？" />
              <div className="grid gap-3" role="radiogroup" aria-label="生成数量">
                {COUNTS.map(({ n, note }) => (
                  <OptionRow
                    key={n}
                    active={preset && form.n === n}
                    onSelect={() => set({ n, custom: false })}
                    title={`${n} 张`}
                    note={note}
                    aside={est(n)}
                  />
                ))}
                <OptionRow
                  active={!preset}
                  onSelect={() => {
                    set({ custom: true })
                    setTimeout(() => customRef.current?.focus(), 0)
                  }}
                  title="其他数量"
                  note={preset ? "1 到 5000 张之间" : undefined}
                  aside={
                    !preset ? (
                      <span className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                        <input
                          ref={customRef}
                          type="number"
                          min={1}
                          max={5000}
                          aria-label="自定义数量"
                          value={form.n || ""}
                          onChange={(e) => set({ n: parseInt(e.target.value || "0", 10) || 0, custom: true })}
                          className="h-10 w-24 rounded-lg border border-input/70 bg-background px-3 text-right text-[17px] tabular outline-none focus:border-primary focus:ring-4 focus:ring-primary/20"
                        />
                        张
                      </span>
                    ) : undefined
                  }
                />
              </div>
              <p className="mt-4 text-sm text-muted-foreground">
                生成过程中可以随时停止，已生成的会保留。预计用时按实测估算
                <Fn n={1} />。
              </p>
            </div>

            {/* 2 · emphasis */}
            <div className="border-t border-hairline py-12">
              <StepTitle lead="侧重。" rest="哪些目标需要多一些？" />
              <div className="grid gap-3" role="radiogroup" aria-label="侧重">
                <OptionRow
                  active={!form.tune}
                  onSelect={() => set({ tune: false })}
                  title="均衡"
                  note="按默认比例，每张图随机组合 2–4 个元素。"
                  aside="推荐"
                />
                <OptionRow
                  active={form.tune}
                  onSelect={() => set({ tune: true })}
                  title="自定义"
                  note="某类目标偏少时，单独调多。"
                />
              </div>
              {low.length > 0 && !form.tune && (
                <p className="mt-4 text-sm text-orange">
                  {low.map(label).join("、")} 偏少。可以选「自定义」把相关元素调多。
                </p>
              )}
              {form.tune && (
                <ul className="mt-6 divide-y divide-hairline rounded-2xl bg-alt px-5">
                  {spec.elements.map((e) => (
                    <li key={e.name} className="flex items-center justify-between gap-4 py-3.5">
                      <div className="min-w-0">
                        <div className="text-[15px]">{e.label}</div>
                        <div className="truncate text-xs text-muted-foreground">{e.shows.map(label).join("、")}</div>
                      </div>
                      <Segmented
                        label={e.label}
                        value={form.factors[e.name] ?? 1}
                        onChange={(v) => setForm((f) => (f ? { ...f, factors: { ...f.factors, [e.name]: v } } : f))}
                      />
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* 3 · batch */}
            <div className="border-t border-hairline py-12">
              <StepTitle lead="批次。" rest="起个名字，留下你的名字。" />
              <div className="grid gap-3">
                <FloatField
                  id="f-batch"
                  label="批次名"
                  value={form.batch}
                  mono
                  invalid={problem.includes("批次")}
                  onChange={(v) => set({ batch: v.trim() })}
                />
                <FloatField
                  id="f-op"
                  label="操作人（你的名字）"
                  value={form.operator}
                  autoComplete="name"
                  onChange={(v) => {
                    store.set("operator", v)
                    set({ operator: v })
                  }}
                />
              </div>
              <p className="mt-3 text-sm text-muted-foreground">批次名用字母、数字、- 或 _，已有的批次不会被覆盖。操作人会记在批次信息里，方便同事知道找谁。</p>

              <button
                type="button"
                onClick={() => setMore((m) => !m)}
                aria-expanded={more}
                className="mt-6 inline-flex items-center gap-2 text-[15px] text-link hover:underline underline-offset-4"
              >
                <span className="grid size-5 place-items-center rounded-full border border-current">
                  {more ? <Minus className="size-3" /> : <Plus className="size-3" />}
                </span>
                更多选项
              </button>
              {more && (
                <div className="mt-4 animate-in fade-in slide-in-from-top-1">
                  <div className="flex gap-3">
                    <FloatField
                      id="f-seed"
                      label="随机种子"
                      value={String(form.seed)}
                      mono
                      inputMode="numeric"
                      onChange={(v) => set({ seed: parseInt(v.replace(/\D/g, "") || "0", 10) })}
                    />
                    <Button variant="secondary" className="h-14 shrink-0 rounded-xl" onClick={() => set({ seed: randomSeed() })}>
                      <Dices />
                      换一个
                    </Button>
                  </div>
                  <p className="mt-3 text-sm text-muted-foreground">数量、种子、侧重都相同，就会生成完全相同的图。想补一批不同的图，换个种子即可。</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      <SummaryBar form={form} rate={rate} problem={problem} starting={starting} onStart={onStart} />
    </>
  )
}

function useCoverage(spec: Spec, form: Form) {
  const [cov, setCov] = useState<Coverage | null>(null)
  const weights = useMemo(() => weightsFor(spec, form), [spec, form])
  const key = JSON.stringify(weights)
  useEffect(() => {
    if (!(form.n >= 1)) return
    let live = true
    const t = window.setTimeout(async () => {
      try {
        const r = await api<Coverage>("/api/preview", {
          spec: spec.name,
          n: Math.min(form.n, 5000),
          seed: form.seed,
          weights: JSON.parse(key),
        })
        if (live) setCov(r)
      } catch {
        /* the preview is a nicety */
      }
    }, 180)
    return () => {
      live = false
      window.clearTimeout(t)
    }
  }, [spec.name, form.n, form.seed, key])
  return cov
}

function OptionRow({
  active,
  onSelect,
  title,
  note,
  aside,
}: {
  active: boolean
  onSelect: () => void
  title: string
  note?: string
  aside?: React.ReactNode
}) {
  return (
    <div
      role="radio"
      aria-checked={active}
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onSelect())}
      className={cn(
        "flex min-h-[72px] cursor-pointer items-center justify-between gap-4 rounded-xl border px-5 py-3.5 transition-[border-color,box-shadow] outline-none select-none",
        "focus-visible:ring-4 focus-visible:ring-primary/25",
        active ? "border-primary shadow-[0_0_0_1px_var(--primary)]" : "border-input/50 hover:border-input",
      )}
    >
      <div className="min-w-0">
        <div className="text-[17px] font-semibold tracking-[-0.02em]">{title}</div>
        {note && <div className={cn("mt-0.5 text-xs", active ? "text-muted-foreground" : "text-faint")}>{note}</div>}
      </div>
      {aside && <div className="shrink-0 text-right text-sm text-muted-foreground tabular">{aside}</div>}
    </div>
  )
}

function Segmented({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex shrink-0 rounded-[9px] bg-foreground/[0.07] p-0.5">
      {FACTORS.map((f) => {
        const on = value === f.v
        return (
          <button
            key={f.v}
            role="radio"
            aria-checked={on}
            onClick={() => onChange(f.v)}
            className={cn(
              "h-7 w-10 rounded-[7px] text-[13px] transition-all",
              on ? "bg-background font-semibold shadow-[0_1px_3px_rgb(0_0_0/0.12),0_0_0_0.5px_rgb(0_0_0/0.04)] dark:bg-[#636366]" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {f.label}
          </button>
        )
      })}
    </div>
  )
}

export function FloatField({
  id,
  label,
  value,
  onChange,
  mono,
  invalid,
  autoComplete = "off",
  inputMode,
  disabled,
}: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
  mono?: boolean
  invalid?: boolean
  autoComplete?: string
  inputMode?: "numeric"
  disabled?: boolean
}) {
  return (
    <div className="relative w-full">
      <input
        id={id}
        value={value}
        placeholder=" "
        spellCheck={false}
        autoComplete={autoComplete}
        inputMode={inputMode}
        disabled={disabled}
        aria-invalid={invalid || undefined}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          "peer h-14 w-full rounded-xl border border-input/70 bg-background px-4 pt-5 pb-1 text-[17px] outline-none transition-[border-color,box-shadow]",
          "focus:border-primary focus:ring-4 focus:ring-primary/20 disabled:bg-alt disabled:text-muted-foreground",
          "aria-invalid:border-destructive aria-invalid:ring-4 aria-invalid:ring-destructive/15",
          mono && "font-mono text-[16px]",
        )}
      />
      <label
        htmlFor={id}
        className={cn(
          "pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-[17px] text-faint transition-all",
          "peer-focus:top-[15px] peer-focus:text-xs peer-[:not(:placeholder-shown)]:top-[15px] peer-[:not(:placeholder-shown)]:text-xs",
        )}
      >
        {label}
      </label>
    </div>
  )
}

function PreviewPanel({ spec, cov, last, low }: { spec: Spec; cov: Coverage | null; last?: BatchInfo; low: string[] }) {
  const label = (c: string) => spec.class_labels[c] ?? c
  const max = cov ? Math.max(1, ...Object.values(cov.coverage)) : 1
  return (
    <div className="rounded-[28px] bg-alt p-5 sm:p-8">
      <div className="relative aspect-[4/3] overflow-hidden rounded-[18px] bg-foreground/5">
        {last?.cover ? (
          <img src={thumbUrl(last.batch, last.cover)} alt={`上一批 ${last.batch} 的样图`} className="size-full object-cover" />
        ) : (
          <div className="grid size-full place-items-center text-faint">
            <BrandGlyph className="size-12" />
          </div>
        )}
      </div>
      <p className="mt-3 text-center text-xs text-muted-foreground">
        {last?.cover ? `上一批 ${last.batch} 的样图。` : "生成后，这里会显示样图。"}
        {spec.title}，{spec.classes.length} 类目标。
      </p>

      <h3 className="mt-8 text-[21px] font-semibold tracking-[-0.02em]">
        这批图会覆盖<span className="text-muted-foreground">，按提示词估算。</span>
      </h3>
      <ul className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 lg:grid-cols-2 xl:grid-cols-3">
        {spec.classes.map((c) => {
          const v = cov?.coverage[c] ?? 0
          const isLow = low.includes(c)
          return (
            <li key={c} title={c}>
              <div className="flex items-baseline justify-between gap-2 text-[13px]">
                <span className={cn("truncate", isLow ? "text-orange" : "text-foreground/85")}>{label(c)}</span>
                <span className={cn("font-semibold tabular", isLow && "text-orange", !cov && "text-faint")}>{cov ? v : "–"}</span>
              </div>
              <div className="mt-1.5 h-[3px] overflow-hidden rounded-full bg-foreground/10">
                <div
                  className={cn("h-full rounded-full transition-[width] duration-500", isLow ? "bg-orange" : "bg-foreground/70")}
                  style={{ width: `${(100 * v) / max}%` }}
                />
              </div>
            </li>
          )
        })}
      </ul>
      <p className="mt-6 text-xs text-muted-foreground">
        模型不一定完全照提示词画，实际以画面为准
        <Fn n={3} />。
      </p>
    </div>
  )
}

function SummaryBar({
  form,
  rate,
  problem,
  starting,
  onStart,
}: {
  form: Form
  rate: Rate
  problem: string
  starting: boolean
  onStart: () => void
}) {
  // keep the footer's footnotes reachable above this fixed bar
  useEffect(() => {
    document.body.style.paddingBottom = "84px"
    return () => {
      document.body.style.paddingBottom = ""
    }
  }, [])
  return (
    <div className="glass fixed inset-x-0 bottom-0 z-40 border-t border-hairline">
      <div className="mx-auto flex max-w-[1024px] items-center justify-between gap-4 px-4 py-3 sm:px-6 sm:py-4">
        <div className="min-w-0" aria-live="polite">
          {problem ? (
            <div className="flex items-center gap-2 text-[15px] text-orange">
              <TriangleAlert className="size-4 shrink-0" />
              <span className="truncate">{problem}</span>
            </div>
          ) : (
            <>
              <div className="truncate text-[17px] font-semibold tracking-[-0.02em]">
                <span className="font-mono text-[16px]">{form.batch}</span> · {form.n} 张
              </div>
              <div className="truncate text-xs text-muted-foreground">
                {rate.sec_per_image
                  ? `约 ${fmtDur(rate.sec_per_image * form.n)} · 约 ${fmtMB((rate.mb_per_image ?? 0) * form.n)} · 按 ${rate.from} 实测`
                  : "生成过一批之后，这里会显示预计用时"}
              </div>
            </>
          )}
        </div>
        <Button size="lg" className="shrink-0" disabled={!!problem || starting} onClick={onStart}>
          {starting && <Loader2 className="animate-spin" />}
          {starting ? "正在启动" : "开始生成"}
        </Button>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ running */

function RunningShowcase({ job, onStop }: { job: Job; onStop: () => void }) {
  const pct = job.total ? job.done / job.total : 0
  const latest = job.recent[job.recent.length - 1]
  const before = job.recent.slice(-5, -1).reverse()
  const [log, setLog] = useState(false)
  return (
    <>
      <section className="bg-black text-[#f5f5f7]">
        <div className="mx-auto max-w-[1024px] px-4 pt-16 pb-20 sm:px-6 sm:pt-24 sm:pb-28">
          <div className="text-center">
            <div className="type-eyebrow inline-flex items-center gap-2 text-[#2997ff]">
              <StatusDot tone="live" className="bg-[#2997ff]" />
              正在生成
            </div>
            <h1 className="type-hero mt-3 font-mono tracking-[-0.04em]">{job.batch}</h1>
            <p className="type-sub mt-3 text-[#a1a1a6]">
              {[job.operator && `${job.operator} 发起`, `共 ${job.total} 张`].filter(Boolean).join(" · ")}
            </p>
          </div>

          <div className="mt-14 grid items-center gap-12 md:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] md:gap-16">
            <div>
              <div className="flex items-baseline gap-2 tabular">
                <span className="text-[104px] leading-none font-semibold tracking-[-0.05em] sm:text-[128px]">{job.done}</span>
                <span className="text-[32px] font-semibold tracking-[-0.03em] text-[#6e6e73]">/ {job.total}</span>
              </div>
              <div
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={job.total}
                aria-valuenow={job.done}
                className="mt-6 h-1 overflow-hidden rounded-full bg-white/15"
              >
                <div className="h-full rounded-full bg-[#2997ff] transition-[width] duration-700" style={{ width: `${pct * 100}%` }} />
              </div>
              <dl className="mt-8 grid grid-cols-2 gap-x-8 gap-y-6">
                <Stat k="已用" v={fmtDur(job.elapsed)} />
                <Stat k="预计还需" v={job.done ? fmtDur(job.eta) : "估算中"} />
                <Stat k="平均每张" v={job.done ? `${(job.elapsed / job.done).toFixed(1)} 秒` : "—"} />
                <Stat k="失败" v={job.errors ? `${job.errors} 张` : "0"} warn={job.errors > 0} />
              </dl>
              <div className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-4">
                <Button
                  variant="outline"
                  className="border-white/30 text-white hover:bg-white/10"
                  onClick={onStop}
                >
                  停止生成
                </Button>
                {job.done > 0 && (
                  <ArrowLink href={href("results", job.batch)} className="text-[17px] text-[#2997ff]">
                    查看已生成的图
                  </ArrowLink>
                )}
              </div>
            </div>

            <div>
              <div className="grid aspect-[4/3] place-items-center overflow-hidden rounded-[28px] bg-[#1d1d1f]">
                {latest ? (
                  <img key={latest} src={thumbUrl(job.batch, latest)} alt={latest} className="size-full animate-in object-cover duration-700 fade-in" />
                ) : (
                  <div className="grid justify-items-center gap-3 px-6 text-center text-sm text-[#86868b]">
                    <Loader2 className="size-5 animate-spin" />
                    第一张要多等一会儿，ComfyUI 正在加载模型。
                  </div>
                )}
              </div>
              <div className="mt-3 flex items-center justify-between text-xs text-[#86868b]">
                <span>最新一张</span>
                {latest && <span className="font-mono">#{shortId(latest)}</span>}
              </div>
              {before.length > 0 && (
                <div className="mt-3 grid grid-cols-4 gap-2">
                  {before.map((id) => (
                    <img key={id} src={thumbUrl(job.batch, id)} alt={id} className="aspect-[4/3] w-full rounded-xl object-cover opacity-80" />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </section>
      <section className="mx-auto max-w-[1024px] px-4 py-10 text-center sm:px-6">
        <p className="text-sm text-muted-foreground">可以关掉这个页面，生成会在后台继续；浏览器标签上会显示进度。</p>
        <button onClick={() => setLog((l) => !l)} className="mt-3 text-sm text-link hover:underline underline-offset-4" aria-expanded={log}>
          {log ? "收起运行日志" : "查看运行日志"}
        </button>
        {log && (
          <pre className="mx-auto mt-4 max-h-72 max-w-[760px] overflow-auto rounded-2xl bg-alt p-4 text-left font-mono text-xs leading-relaxed whitespace-pre-wrap text-muted-foreground">
            {job.log.join("\n") || "…"}
          </pre>
        )}
      </section>
    </>
  )
}

function Stat({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-[#86868b]">{k}</dt>
      <dd className={cn("mt-1 text-[21px] font-semibold tracking-[-0.02em] tabular", warn && "text-[#ff9f0a]")}>{v}</dd>
    </div>
  )
}

function FinishedRibbon({ job, onClose }: { job: Job; onClose: () => void }) {
  const tone = job.status === "done" ? "ok" : job.status === "cancelled" ? "warn" : "bad"
  return (
    <>
      <Ribbon tone={tone} onClose={onClose}>
        {job.status === "done" && <>{job.batch} 已完成：{job.done} 张，用时 {fmtDur(job.elapsed)}。 </>}
        {job.status === "cancelled" && <>{job.batch} 已停止，已生成的 {job.done} 张都保留了。 </>}
        {job.status === "failed" && <>{job.batch} 生成失败。下面是最后几行日志，可以截图发给管理员。 </>}
        {job.done > 0 && <ArrowLink href={href("results", job.batch)}>去看图</ArrowLink>}
      </Ribbon>
      {job.status === "failed" && (
        <pre className="mx-auto max-w-[1024px] overflow-auto bg-danger-soft px-6 pb-4 font-mono text-xs whitespace-pre-wrap">
          {job.log.slice(-12).join("\n")}
        </pre>
      )}
    </>
  )
}
