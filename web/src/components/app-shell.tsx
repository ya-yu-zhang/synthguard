import { useEffect, useState, type ReactNode } from "react"
import { Monitor, Moon, Sun } from "lucide-react"
import { cn } from "@/lib/utils"
import { useApp } from "@/app-context"
import { gpuShort } from "@/lib/format"
import { href, type Page } from "@/lib/route"
import type { Theme } from "@/hooks/use-theme"
import { BrandGlyph, StatusDot } from "@/components/bits"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

// New sections add a line here.
const NAV: { page: Page; label: string }[] = [
  { page: "generate", label: "生成" },
  { page: "results", label: "结果" },
  { page: "env", label: "环境与迁移" },
]

export function AppShell({ page, children }: { page: Page; children: ReactNode }) {
  return (
    <div className="flex min-h-svh flex-col">
      <GlobalNav page={page} />
      <main className="flex-1">{children}</main>
      <SiteFooter />
    </div>
  )
}

function GlobalNav({ page }: { page: Page }) {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : ""
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false)
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open])
  return (
    <header className={cn("sticky top-0 z-50 h-11", open ? "bg-background" : "glass")}>
      <nav aria-label="全站" className="mx-auto flex h-full max-w-[1024px] items-center justify-between px-4 sm:px-6">
        <a href={href("generate")} className="flex items-center gap-2 text-foreground/90 hover:text-foreground" aria-label="SynthGuard 首页">
          <BrandGlyph className="size-[17px]" />
          <span className="text-[13px] font-semibold tracking-[-0.01em]">SynthGuard</span>
        </a>
        <ul className="hidden items-center gap-9 md:flex">
          {NAV.map((n) => (
            <li key={n.page}>
              <a
                href={href(n.page)}
                aria-current={n.page === page ? "page" : undefined}
                className={cn(
                  "text-xs transition-colors",
                  n.page === page ? "text-foreground" : "text-foreground/70 hover:text-foreground",
                )}
              >
                {n.label}
              </a>
            </li>
          ))}
        </ul>
        <div className="flex items-center gap-1">
          <MachineStatus />
          <ThemeButton />
          <button
            className="grid size-9 place-items-center md:hidden"
            aria-label={open ? "关闭菜单" : "打开菜单"}
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
          >
            <span className="relative block h-3 w-4">
              <span className={cn("absolute left-0 h-px w-4 bg-foreground transition-all", open ? "top-1.5 rotate-45" : "top-0.5")} />
              <span className={cn("absolute left-0 h-px w-4 bg-foreground transition-all", open ? "top-1.5 -rotate-45" : "top-2.5")} />
            </span>
          </button>
        </div>
      </nav>

      {open && (
        <div className="fixed inset-x-0 top-11 bottom-0 z-50 overflow-y-auto bg-background px-10 pt-6 md:hidden">
          <ul className="space-y-3">
            {NAV.map((n, i) => (
              <li key={n.page} className="animate-in fade-in slide-in-from-top-2 fill-mode-both" style={{ animationDelay: `${i * 40}ms` }}>
                <a href={href(n.page)} onClick={() => setOpen(false)} className="text-[28px] font-semibold tracking-[-0.02em]">
                  {n.label}
                </a>
              </li>
            ))}
          </ul>
          <MachineDetail className="mt-10" />
        </div>
      )}
    </header>
  )
}

function MachineStatus() {
  const { state, running } = useApp()
  if (!state) return null
  const pct = running ? Math.round((100 * running.done) / running.total) : 0
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <a
          href={href(running ? "generate" : "env")}
          className="flex h-9 items-center gap-1.5 rounded-full px-2.5 text-xs text-foreground/75 hover:text-foreground"
        >
          <StatusDot tone={running ? "live" : state.comfy_online ? "ok" : "bad"} />
          <span className="tabular">{running ? `生成中 ${pct}%` : state.comfy_online ? "在线" : "未连接"}</span>
        </a>
      </TooltipTrigger>
      <TooltipContent>
        <MachineDetail />
      </TooltipContent>
    </Tooltip>
  )
}

function MachineDetail({ className }: { className?: string }) {
  const { state, running } = useApp()
  if (!state) return null
  const gpu = state.comfy_devices.map(gpuShort).join(" + ")
  return (
    <div className={cn("text-xs leading-relaxed", className)}>
      <div>{state.comfy_online ? "ComfyUI 在线" : "ComfyUI 未连接"}</div>
      <div className="opacity-70">{[state.host, gpu].filter(Boolean).join(" · ")}</div>
      {running && (
        <div className="opacity-70">
          正在生成 {running.batch} · {running.done}/{running.total}
        </div>
      )}
    </div>
  )
}

const THEMES: { t: Theme; label: string; icon: typeof Sun }[] = [
  { t: "system", label: "外观：跟随系统", icon: Monitor },
  { t: "light", label: "外观：浅色", icon: Sun },
  { t: "dark", label: "外观：深色", icon: Moon },
]

function ThemeButton() {
  const { theme, setTheme } = useApp()
  const i = THEMES.findIndex((x) => x.t === theme)
  const cur = THEMES[i < 0 ? 0 : i]
  const next = THEMES[(i + 1) % THEMES.length]
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={() => setTheme(next.t)}
          aria-label={`${cur.label}，点一下切换`}
          className="grid size-9 place-items-center rounded-full text-foreground/70 hover:text-foreground"
        >
          <cur.icon className="size-[15px]" strokeWidth={1.8} />
        </button>
      </TooltipTrigger>
      <TooltipContent>{cur.label}</TooltipContent>
    </Tooltip>
  )
}

function SiteFooter() {
  const { state } = useApp()
  return (
    <footer className="bg-alt">
      <div className="type-caption mx-auto max-w-[1024px] px-4 py-6 text-muted-foreground sm:px-6">
        <ol className="space-y-2 border-b border-border pb-4">
          <li id="fn-1">1. 预计用时和占用空间，按这台机器上一批（10 张以上）的实测速度估算，第一张图还要加上加载模型的时间。</li>
          <li id="fn-2">2. 「我已看过」只记在你自己的浏览器里，每个人一份，换电脑或清理浏览器数据后会重新开始。</li>
          <li id="fn-3">3. 生成的图片不带标注框。提示词要求的目标，模型不一定都画出来，标注以画面为准。</li>
        </ol>
        <div className="flex flex-wrap justify-between gap-2 pt-4">
          <span>SynthGuard 生图台 · 合成数据工厂</span>
          {state && <span>{[state.host, state.gen_profile && `配置 ${state.gen_profile}`].filter(Boolean).join(" · ")}</span>}
        </div>
      </div>
    </footer>
  )
}
