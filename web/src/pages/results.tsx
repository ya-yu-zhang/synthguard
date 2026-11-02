import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Dialog as DialogPrimitive } from "radix-ui"
import { Check, ChevronLeft, ChevronRight, Copy, Loader2, X } from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { useApp } from "@/app-context"
import { useResource } from "@/hooks/use-resource"
import {
  api,
  downloadUrl,
  imageUrl,
  thumbUrl,
  type BatchDetail,
  type BatchInfo,
  type Row,
  type Spec,
  type Specs,
} from "@/lib/api"
import { fmtDur, fmtMB, shortId, shortTime, STATUS_TEXT } from "@/lib/format"
import { href } from "@/lib/route"
import { copyText, seen as seenStore } from "@/lib/store"
import { ArrowLink, BrandGlyph, Fn, Hero, LocalNav, Ribbon } from "@/components/bits"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export function ResultsPage({ param }: { param?: string }) {
  const { epoch, running } = useApp()
  const list = useResource<{ batches: BatchInfo[] }>("/api/batches", epoch)
  const specs = useResource<Specs>("/api/specs")
  const batches = list.data?.batches
  const name = batches?.some((b) => b.batch === param) ? param : batches?.[0]?.batch
  const detail = useResource<BatchDetail>(name ? `/api/batches/${encodeURIComponent(name)}` : null, epoch)
  const data = detail.data?.info.batch === name ? detail.data : null

  // new images appear while this batch is still generating
  const liveDone = running && running.batch === name ? running.done : -1
  const { reload } = detail
  useEffect(() => {
    if (liveDone > 0) void reload()
  }, [liveDone, reload])

  if (list.error)
    return (
      <>
        <LocalNav title="结果" />
        <Ribbon tone="bad">读不到批次列表：{list.error}</Ribbon>
      </>
    )
  if (batches && batches.length === 0) return <EmptyState />

  return data ? (
    <BatchView key={data.info.batch} data={data} batches={batches ?? []} spec={specs.data?.specs[0]} setData={detail.setData} />
  ) : (
    <>
      <LocalNav title="结果" />
      <div className="mx-auto max-w-[1024px] space-y-6 px-4 pt-20 sm:px-6">
        <Skeleton className="mx-auto h-14 w-2/3 rounded-2xl" />
        <Skeleton className="mx-auto h-6 w-1/3" />
        <div className="grid grid-cols-2 gap-3 pt-10 sm:grid-cols-4">
          {Array.from({ length: 8 }, (_, i) => (
            <Skeleton key={i} className="aspect-[4/3] w-full rounded-[18px]" />
          ))}
        </div>
      </div>
    </>
  )
}

function EmptyState() {
  return (
    <>
      <LocalNav title="结果" />
      <Hero title="还没有图片。" sub="先生成 20 张试试，看看画面，再决定要不要批量。">
        <Button size="lg" asChild>
          <a href={href("generate")}>去生成</a>
        </Button>
      </Hero>
    </>
  )
}

type Filter = "all" | "rejected" | string

function BatchView({
  data,
  batches,
  spec,
  setData,
}: {
  data: BatchDetail
  batches: BatchInfo[]
  spec?: Spec
  setData: (d: BatchDetail) => void
}) {
  const { info, rows } = data
  const rejected = useMemo(() => new Set(data.rejected), [data.rejected])
  const [filter, setFilter] = useState<Filter>("all")
  const [lb, setLb] = useState<number | null>(null)
  const [mine, setMine] = useState(() => seenStore.get(info.batch))
  const label = (c: string) => spec?.class_labels[c] ?? c

  const items = useMemo(
    () =>
      filter === "all"
        ? rows
        : filter === "rejected"
          ? rows.filter((r) => rejected.has(r.id))
          : rows.filter((r) => r.requested_classes.includes(filter)),
    [rows, filter, rejected],
  )
  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    rows.forEach((r) => r.requested_classes.forEach((k) => (c[k] = (c[k] ?? 0) + 1)))
    return c
  }, [rows])
  const classes = (spec?.classes ?? Object.keys(counts)).filter((c) => counts[c])
  const seenN = rows.filter((r) => mine.has(r.id)).length
  const keep = rows.length - data.rejected.length
  const firstUnseen = rows.findIndex((r) => !mine.has(r.id))
  const left = rows.length - seenN

  const markSeen = useCallback(
    (id: string) => {
      if (seenStore.add(info.batch, id)) setMine(seenStore.get(info.batch))
    },
    [info.batch],
  )

  async function toggleReject(r: Row) {
    const on = !rejected.has(r.id)
    try {
      const res = await api<{ rejected: string[] }>(`/api/batches/${encodeURIComponent(info.batch)}/reject`, {
        ids: [r.id],
        rejected: on,
      })
      setData({ ...data, rejected: res.rejected, info: { ...info, rejected: res.rejected.length } })
      toast(on ? "已标为不合格" : "已恢复为合格", { description: on ? "不会放进标注包，原图不删" : undefined })
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const review = () => {
    setFilter("all")
    setLb(Math.max(0, firstUnseen))
  }

  const headline =
    rows.length === 0 ? "这一批还没有图。" : left === 0 ? `${rows.length} 张图，都看过了。` : seenN ? `还有 ${left} 张，没看。` : `${rows.length} 张图，等你挑。`
  const meta = [
    info.operator && `${info.operator} 生成`,
    (info.started || info.finished || "").slice(0, 16),
    fmtMB(info.size_mb),
  ].filter(Boolean)

  return (
    <>
      <LocalNav title={<span className="font-mono">{info.batch}</span>}>
        {rows.length > 0 && (
          <button onClick={review} className="hidden text-foreground/75 hover:text-foreground sm:inline">
            {firstUnseen < 0 ? "从头再看" : seenN ? "继续看图" : "开始看图"}
          </button>
        )}
        {keep > 0 && (
          <Button size="sm" asChild>
            <a href={downloadUrl(info.batch)} download={`${info.batch}_labeling.zip`}>
              下载标注包
            </a>
          </Button>
        )}
      </LocalNav>

      {info.status === "running" && (
        <Ribbon>
          <Loader2 className="mr-1.5 inline size-3.5 animate-spin align-[-2px]" />
          这一批还在生成，新图会自动出现在这里。
        </Ribbon>
      )}
      {info.status === "cancelled" && (
        <Ribbon tone="warn">
          这一批中途停止了：计划 {info.n ?? "?"} 张，实际 {rows.length} 张。已有的图可以照常使用。
        </Ribbon>
      )}

      <Hero eyebrow={info.status && info.status !== "done" ? STATUS_TEXT[info.status] : info.batch} title={headline} sub={meta.join(" · ")}>
        {rows.length > 0 && (
          <Button size="lg" onClick={review}>
            {firstUnseen < 0 ? "从头再看" : seenN ? "继续看图" : "开始看图"}
          </Button>
        )}
        {keep > 0 && (
          <ArrowLink href={downloadUrl(info.batch)} download={`${info.batch}_labeling.zip`} className="text-[17px]">
            下载标注包 · {keep} 张
          </ArrowLink>
        )}
      </Hero>

      <Numbers
        items={[
          { v: String(rows.length), k: "张图片" },
          { v: `${seenN}`, unit: `/${rows.length}`, k: (
              <>
                我已看过
                <Fn n={2} />
              </>
            ) },
          { v: String(data.rejected.length), k: data.rejected.length ? "张不合格，不进标注包" : "张不合格" },
          { v: info.seconds ? fmtDur(info.seconds) : "—", k: info.seconds && rows.length ? `用时，每张 ${(info.seconds / rows.length).toFixed(1)} 秒` : "用时" },
        ]}
      />

      {batches.length > 1 && <BatchCarousel batches={batches} current={info.batch} />}

      <section className="mx-auto max-w-[1200px] px-4 pt-6 pb-24 sm:px-6">
        {/* mx-auto, not justify-center: centred when it fits, scrollable from the start when it doesn't */}
        <div className="no-scrollbar -mx-4 mb-8 flex overflow-x-auto px-4">
          <div className="mx-auto inline-flex shrink-0 gap-0.5 rounded-full bg-foreground/[0.06] p-1" role="toolbar" aria-label="按类别筛选">
            <Pill active={filter === "all"} onClick={() => setFilter("all")} label="全部" n={rows.length} />
            {classes.map((c) => (
              <Pill key={c} active={filter === c} onClick={() => setFilter(c)} label={label(c)} n={counts[c]} />
            ))}
            {data.rejected.length > 0 && (
              <Pill active={filter === "rejected"} onClick={() => setFilter("rejected")} label="不合格" n={data.rejected.length} />
            )}
          </div>
        </div>

        {items.length ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {items.map((r, i) => (
              <button
                key={r.id}
                data-id={r.id}
                onClick={() => setLb(i)}
                aria-label={`查看 ${r.id}`}
                className="group relative aspect-[4/3] cursor-zoom-in overflow-hidden rounded-[18px] bg-alt outline-none focus-visible:ring-4 focus-visible:ring-primary/40"
              >
                <img
                  src={thumbUrl(info.batch, r.id)}
                  alt=""
                  loading="lazy"
                  decoding="async"
                  className={cn(
                    "size-full object-cover transition-transform duration-500 ease-out group-hover:scale-[1.03]",
                    rejected.has(r.id) && "opacity-30 grayscale",
                  )}
                />
                <span className="absolute bottom-2 left-2.5 font-mono text-[11px] text-white/0 drop-shadow transition-colors group-hover:text-white group-focus-visible:text-white">
                  #{shortId(r.id)}
                </span>
                {mine.has(r.id) && (
                  <span className="absolute right-2 bottom-2 grid size-5 place-items-center rounded-full bg-black/45 text-white backdrop-blur" title="看过">
                    <Check className="size-3" strokeWidth={3} />
                  </span>
                )}
                {rejected.has(r.id) && (
                  <span className="absolute top-2.5 left-2.5 rounded-full bg-black/70 px-2.5 text-[11px] leading-[22px] text-white backdrop-blur">
                    不合格
                  </span>
                )}
              </button>
            ))}
          </div>
        ) : (
          <p className="py-20 text-center text-muted-foreground">这个筛选下没有图片。</p>
        )}
        <p className="mt-10 text-center text-xs text-muted-foreground">
          标签是提示词要求出现的目标，仅供参考，标注以画面为准
          <Fn n={3} />。
        </p>
      </section>

      {lb !== null && items[lb] && (
        <Lightbox
          items={items}
          index={lb}
          setIndex={setLb}
          batch={info.batch}
          label={label}
          rejected={rejected}
          onToggleReject={toggleReject}
          onSeen={markSeen}
          onClose={() => setLb(null)}
        />
      )}
    </>
  )
}

function Numbers({ items }: { items: { v: string; unit?: string; k: React.ReactNode }[] }) {
  return (
    <section className="border-y border-hairline">
      <dl className="mx-auto grid max-w-[1024px] grid-cols-2 gap-y-10 px-4 py-12 text-center sm:grid-cols-4 sm:px-6">
        {items.map((it, i) => (
          <div key={i}>
            <dd className="text-[40px] leading-none font-semibold tracking-[-0.035em] tabular sm:text-[48px]">
              {it.v}
              {it.unit && <span className="text-[24px] text-muted-foreground">{it.unit}</span>}
            </dd>
            <dt className="mt-2 text-sm text-muted-foreground">{it.k}</dt>
          </div>
        ))}
      </dl>
    </section>
  )
}

function BatchCarousel({ batches, current }: { batches: BatchInfo[]; current: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const scroll = (d: number) => ref.current?.scrollBy({ left: d * 300, behavior: "smooth" })
  return (
    <section className="bg-alt py-14">
      <div className="mx-auto flex max-w-[1200px] items-end justify-between px-4 sm:px-6">
        <h2 className="type-headline">全部批次。</h2>
        <div className="hidden gap-2 sm:flex">
          <Button variant="secondary" size="icon-sm" onClick={() => scroll(-1)} aria-label="向左">
            <ChevronLeft />
          </Button>
          <Button variant="secondary" size="icon-sm" onClick={() => scroll(1)} aria-label="向右">
            <ChevronRight />
          </Button>
        </div>
      </div>
      <div ref={ref} className="no-scrollbar mt-8 flex snap-x gap-5 overflow-x-auto scroll-px-6 px-4 sm:px-[max(24px,calc((100vw-1200px)/2+24px))]">
        {batches.map((b) => {
          const active = b.batch === current
          return (
            <a
              key={b.batch}
              href={href("results", b.batch)}
              aria-current={active ? "page" : undefined}
              className={cn(
                "w-[280px] shrink-0 snap-start overflow-hidden rounded-[18px] bg-tile transition-shadow",
                active ? "shadow-[0_0_0_2px_var(--primary)]" : "hover:shadow-[0_8px_30px_rgb(0_0_0/0.08)]",
              )}
            >
              <div className="aspect-[4/3] bg-foreground/5">
                {b.cover ? (
                  <img src={thumbUrl(b.batch, b.cover)} alt="" loading="lazy" className="size-full object-cover" />
                ) : (
                  <div className="grid size-full place-items-center text-faint">
                    <BrandGlyph className="size-8" />
                  </div>
                )}
              </div>
              <div className="p-5">
                {b.status && b.status !== "done" && <div className="mb-1 text-xs font-semibold text-orange">{STATUS_TEXT[b.status]}</div>}
                <div className="font-mono text-[17px] font-semibold">{b.batch}</div>
                <div className="mt-1 text-sm text-muted-foreground tabular">
                  {[`${b.images} 张`, b.rejected ? `${b.rejected} 不合格` : null, shortTime(b.started || b.finished), b.operator]
                    .filter(Boolean)
                    .join(" · ")}
                </div>
              </div>
            </a>
          )
        })}
      </div>
    </section>
  )
}

function Pill({ active, onClick, label, n }: { active: boolean; onClick: () => void; label: string; n: number }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex h-8 shrink-0 items-center gap-1.5 rounded-full px-3.5 text-[13px] whitespace-nowrap transition-all outline-none focus-visible:ring-2 focus-visible:ring-primary",
        active ? "bg-background font-semibold shadow-[0_1px_4px_rgb(0_0_0/0.12)] dark:bg-[#48484a]" : "text-foreground/70 hover:text-foreground",
      )}
    >
      {label}
      <span className={cn("text-xs tabular", active ? "text-muted-foreground" : "text-faint")}>{n}</span>
    </button>
  )
}

/* ------------------------------------------------------------------ lightbox */

function Lightbox({
  items,
  index,
  setIndex,
  batch,
  label,
  rejected,
  onToggleReject,
  onSeen,
  onClose,
}: {
  items: Row[]
  index: number
  setIndex: (i: number) => void
  batch: string
  label: (c: string) => string
  rejected: Set<string>
  onToggleReject: (r: Row) => void
  onSeen: (id: string) => void
  onClose: () => void
}) {
  const r = items[index]
  const isRej = rejected.has(r.id)
  const move = (d: number) => setIndex((index + d + items.length) % items.length)

  useEffect(() => {
    onSeen(r.id)
    const next = items[(index + 1) % items.length]
    if (next) new Image().src = imageUrl(batch, next.id) // preload
  }, [r.id, index, items, batch, onSeen])

  return (
    <DialogPrimitive.Root open onOpenChange={(o) => !o && onClose()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className="fixed inset-0 z-50 grid grid-rows-[minmax(0,1fr)_auto] text-[#f5f5f7] outline-none lg:grid-cols-[minmax(0,1fr)_380px] lg:grid-rows-1"
          onKeyDown={(e) => {
            if (e.key === "ArrowLeft") move(-1)
            else if (e.key === "ArrowRight") move(1)
            else if (e.key.toLowerCase() === "x" && !e.ctrlKey && !e.metaKey) onToggleReject(r)
          }}
          onCloseAutoFocus={(e) => {
            // return focus to the tile of the image the reviewer stopped on
            e.preventDefault()
            const tile = document.querySelector<HTMLElement>(`[data-id="${r.id}"]`)
            tile?.focus({ preventScroll: true })
            tile?.scrollIntoView({ block: "nearest" })
          }}
        >
          <DialogPrimitive.Title className="sr-only">{r.id}</DialogPrimitive.Title>
          <div className="relative grid min-h-0 place-items-center p-4 sm:px-20 sm:py-12" onClick={(e) => e.target === e.currentTarget && onClose()}>
            <img
              key={r.id}
              src={imageUrl(batch, r.id)}
              alt={r.id}
              className={cn("max-h-full max-w-full animate-in rounded-[18px] object-contain duration-300 fade-in", isRej && "opacity-50")}
            />
            {items.length > 1 && (
              <>
                <NavBtn side="left" onClick={() => move(-1)} />
                <NavBtn side="right" onClick={() => move(1)} />
              </>
            )}
            <div className="absolute top-4 left-1/2 -translate-x-1/2 text-xs text-[#86868b] tabular">
              {index + 1} / {items.length}
            </div>
          </div>

          <aside className="flex max-h-[50svh] min-h-0 flex-col bg-[#1d1d1f] lg:max-h-none">
            <div className="flex items-center justify-between gap-3 px-6 pt-5">
              <span className="font-mono text-xs text-[#a1a1a6]">{r.id}</span>
              <DialogPrimitive.Close asChild>
                <button className="grid size-8 place-items-center rounded-full bg-white/10 text-white hover:bg-white/20" aria-label="关闭（Esc）">
                  <X className="size-4" />
                </button>
              </DialogPrimitive.Close>
            </div>

            <div className="no-scrollbar flex-1 space-y-7 overflow-y-auto px-6 pt-5 pb-6">
              <div>
                <div className="type-title">{isRej ? "已标为不合格。" : `#${shortId(r.id)}`}</div>
                <div className="mt-1 text-sm text-[#a1a1a6] tabular">
                  {r.w} × {r.h} · 种子 {r.seed} · {r.steps} 步
                </div>
              </div>
              <div>
                <div className="mb-2.5 text-xs text-[#86868b]">提示词要求出现（仅供参考，以画面为准）</div>
                <div className="flex flex-wrap gap-1.5">
                  {r.requested_classes.map((c) => (
                    <span key={c} className="rounded-full bg-white/10 px-3 text-[13px] leading-7">
                      {label(c)}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <div className="mb-2.5 flex items-center justify-between text-xs text-[#86868b]">
                  提示词
                  <button
                    className="inline-flex items-center gap-1 text-[#2997ff] hover:underline"
                    onClick={async () => {
                      await copyText(r.prompt)
                      toast("已复制提示词")
                    }}
                  >
                    <Copy className="size-3" />
                    复制
                  </button>
                </div>
                <p className="text-[13px] leading-relaxed text-[#a1a1a6]">{r.prompt}</p>
              </div>
              <div className="text-xs text-[#86868b]">模型 {r.model}</div>
            </div>

            <div className="space-y-3 border-t border-white/10 px-6 py-5">
              <Button
                size="lg"
                className={cn("w-full", isRej ? "bg-white/15 text-white hover:bg-white/25" : "bg-[#f5f5f7] text-black hover:bg-white")}
                onClick={() => onToggleReject(r)}
              >
                {isRej ? "恢复为合格" : "标为不合格"}
                <kbd className="ml-1 rounded border border-current/30 px-1.5 font-mono text-[11px] opacity-60">X</kbd>
              </Button>
              <p className="text-center text-xs text-[#86868b]">← → 翻页 · 不合格的图不进标注包，原图不删</p>
            </div>
          </aside>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

function NavBtn({ side, onClick }: { side: "left" | "right"; onClick: () => void }) {
  const Icon = side === "left" ? ChevronLeft : ChevronRight
  return (
    <button
      onClick={onClick}
      aria-label={side === "left" ? "上一张" : "下一张"}
      className={cn(
        "absolute top-1/2 hidden size-12 -translate-y-1/2 place-items-center rounded-full bg-white/10 text-white backdrop-blur transition-colors hover:bg-white/20 sm:grid",
        side === "left" ? "left-4" : "right-4",
      )}
    >
      <Icon className="size-5" />
    </button>
  )
}
