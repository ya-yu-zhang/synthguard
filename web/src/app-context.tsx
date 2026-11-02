import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { toast } from "sonner"
import { api, type AppState, type Job } from "@/lib/api"
import { useTheme, type Theme } from "@/hooks/use-theme"

type Ctx = {
  state: AppState | null
  running: Job | null
  /** a job that ended while this page was open (for the "done" banner) */
  finished: Job | null
  clearFinished: () => void
  /** bumps whenever a job starts or ends, so pages refetch batches and estimates */
  epoch: number
  bump: () => void
  refresh: () => Promise<void>
  theme: Theme
  resolvedTheme: "light" | "dark"
  setTheme: (t: Theme) => void
}

const AppContext = createContext<Ctx | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AppState | null>(null)
  const [finished, setFinished] = useState<Job | null>(null)
  const [epoch, setEpoch] = useState(0)
  const prevJob = useRef<Job | null>(null)
  const timer = useRef<number | undefined>(undefined)
  const { theme, resolved, setTheme } = useTheme()

  const refresh = useCallback(async () => {
    window.clearTimeout(timer.current)
    let next: AppState | null = null
    try {
      next = await api<AppState>("/api/state")
    } catch {
      /* server restarting: keep showing the last state */
    }
    if (next) {
      const before = prevJob.current
      const job = next.job
      if (before?.status === "running" && job && job.status !== "running") {
        setFinished(job)
        setEpoch((e) => e + 1)
        if (job.status === "done") toast.success(`${job.batch} 生成完成`, { description: `共 ${job.done} 张` })
        else if (job.status === "cancelled") toast.warning(`${job.batch} 已停止`, { description: `已生成的 ${job.done} 张都保留了` })
        else toast.error(`${job.batch} 生成失败`, { description: "到「生成」页查看日志" })
      }
      prevJob.current = job
      setState(next)
    }
    const isRunning = next?.job?.status === "running"
    timer.current = window.setTimeout(() => void refresh(), isRunning ? 2000 : 8000)
  }, [])

  useEffect(() => {
    void refresh()
    return () => window.clearTimeout(timer.current)
  }, [refresh])

  const running = state?.job?.status === "running" ? state.job : null

  // progress in the browser tab, so a long batch can run in the background
  useEffect(() => {
    const set = () => {
      if (running) document.title = `${Math.round((100 * running.done) / running.total)}% · ${running.batch} 生成中`
      else if (finished && document.hidden)
        document.title = `${finished.status === "done" ? "✓ 完成" : "已停止"} · ${finished.batch}`
      else document.title = "SynthGuard 生图台"
    }
    set()
    document.addEventListener("visibilitychange", set)
    return () => document.removeEventListener("visibilitychange", set)
  }, [running, finished])

  const value = useMemo<Ctx>(
    () => ({
      state,
      running,
      finished,
      clearFinished: () => setFinished(null),
      epoch,
      bump: () => setEpoch((e) => e + 1),
      refresh,
      theme,
      resolvedTheme: resolved,
      setTheme,
    }),
    [state, running, finished, epoch, refresh, theme, resolved, setTheme],
  )
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error("useApp outside AppProvider")
  return ctx
}
