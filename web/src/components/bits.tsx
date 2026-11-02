import { useEffect, useState, type ReactNode } from "react"
import { ChevronRight, X } from "lucide-react"
import { cn } from "@/lib/utils"

/** SynthGuard glyph: a bolt in the ink color, the way a product site carries its mark. */
export function BrandGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-4 fill-current", className)} aria-hidden>
      <path d="M18 3 7 18.5h7.5L12.5 29 25 12.5h-7.5z" />
    </svg>
  )
}

export function StatusDot({ tone, className }: { tone: "ok" | "bad" | "live" | "idle"; className?: string }) {
  return (
    <span
      className={cn(
        "inline-block size-[7px] shrink-0 rounded-full",
        tone === "ok" && "bg-success",
        tone === "bad" && "bg-destructive",
        tone === "live" && "animate-live bg-live",
        tone === "idle" && "bg-faint",
        className,
      )}
    />
  )
}

/** "了解更多 ›" style text link. */
export function ArrowLink({
  href,
  children,
  className,
  onClick,
  download,
}: {
  href?: string
  children: ReactNode
  className?: string
  onClick?: () => void
  download?: string | boolean
}) {
  const inner = (
    <>
      {children}
      <ChevronRight className="size-[0.95em] translate-y-[0.5px] transition-transform group-hover:translate-x-0.5" strokeWidth={2.4} />
    </>
  )
  const cls = cn("group inline-flex items-center gap-0.5 text-link hover:underline underline-offset-4", className)
  return href ? (
    <a href={href} className={cls} onClick={onClick} download={download === true ? "" : download || undefined}>
      {inner}
    </a>
  ) : (
    <button type="button" className={cls} onClick={onClick}>
      {inner}
    </button>
  )
}

function useScrolled(y = 8) {
  const [s, setS] = useState(false)
  useEffect(() => {
    const f = () => setS(window.scrollY > y)
    f()
    window.addEventListener("scroll", f, { passive: true })
    return () => window.removeEventListener("scroll", f)
  }, [y])
  return s
}

/** The page's own sticky bar under the global nav: title left, links and one pill right. */
export function LocalNav({ title, children }: { title: ReactNode; children?: ReactNode }) {
  const scrolled = useScrolled()
  return (
    <div
      className={cn(
        "glass sticky top-11 z-40 border-b transition-colors",
        scrolled ? "border-hairline" : "border-transparent",
      )}
    >
      <div className="mx-auto flex h-[52px] max-w-[1024px] items-center justify-between gap-4 px-4 sm:px-6">
        <div className="truncate text-[21px] font-semibold tracking-[-0.02em]">{title}</div>
        <div className="flex shrink-0 items-center gap-4 text-xs">{children}</div>
      </div>
    </div>
  )
}

/** Thin full-width notice under the local nav. */
export function Ribbon({
  tone = "info",
  children,
  onClose,
}: {
  tone?: "info" | "ok" | "warn" | "bad"
  children: ReactNode
  onClose?: () => void
}) {
  return (
    <div
      role={tone === "bad" ? "alert" : "status"}
      className={cn(
        "relative px-10 py-3 text-center text-sm",
        tone === "info" && "bg-alt",
        tone === "ok" && "bg-success-soft",
        tone === "warn" && "bg-warning-soft",
        tone === "bad" && "bg-danger-soft",
      )}
    >
      {children}
      {onClose && (
        <button
          onClick={onClose}
          aria-label="关闭提示"
          className="absolute top-1/2 right-3 grid size-7 -translate-y-1/2 place-items-center rounded-full text-muted-foreground hover:bg-foreground/5"
        >
          <X className="size-4" />
        </button>
      )}
    </div>
  )
}

export function Hero({
  eyebrow,
  title,
  sub,
  children,
  className,
}: {
  eyebrow?: ReactNode
  title: ReactNode
  sub?: ReactNode
  children?: ReactNode
  className?: string
}) {
  return (
    <section className={cn("px-4 pt-14 pb-12 text-center sm:pt-20 sm:pb-16", className)}>
      {eyebrow && <div className="type-eyebrow mb-3 text-orange">{eyebrow}</div>}
      <h1 className="type-hero mx-auto max-w-[16em] text-balance">{title}</h1>
      {sub && <p className="type-sub mx-auto mt-4 max-w-[34em] text-pretty text-muted-foreground">{sub}</p>}
      {children && <div className="mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-3">{children}</div>}
    </section>
  )
}

/** "**数量。**这一批要多少张？" — bold lead-in, grey continuation. */
export function StepTitle({ lead, rest }: { lead: string; rest: string }) {
  return (
    <h2 className="type-title mb-6">
      {lead}
      <span className="text-muted-foreground">{rest}</span>
    </h2>
  )
}

/** Superscript footnote marker; the notes themselves live in the site footer. */
export function Fn({ n }: { n: number }) {
  return (
    <sup className="ml-px text-[0.6em] font-normal text-muted-foreground">
      <a href={`#fn-${n}`} onClick={(e) => (e.preventDefault(), document.getElementById(`fn-${n}`)?.scrollIntoView({ behavior: "smooth" }))}>
        {n}
      </a>
    </sup>
  )
}
