import type { JobStatus } from "./api"

export function fmtDur(sec: number | null | undefined): string {
  if (sec === null || sec === undefined || Number.isNaN(sec)) return "—"
  const s = Math.round(sec)
  if (s < 60) return `${s} 秒`
  const m = Math.round(s / 60)
  if (m < 60) return `${m} 分钟`
  const h = Math.floor(m / 60)
  const mm = m % 60
  return mm ? `${h} 小时 ${mm} 分` : `${h} 小时`
}

export const fmtMB = (mb: number) => (mb >= 1000 ? `${(mb / 1000).toFixed(1)} GB` : `${Math.max(1, Math.round(mb))} MB`)

// "cuda:0 NVIDIA GeForce RTX 5070 : cudaMallocAsync" -> "RTX 5070"
export const gpuShort = (name: string) =>
  name.replace(/^cuda:\d+\s*/, "").replace(/\s*:.*$/, "").replace(/^NVIDIA (GeForce )?/, "")

export const STATUS_TEXT: Record<JobStatus, string> = {
  done: "完成",
  running: "生成中",
  cancelled: "已停止",
  failed: "失败",
}

export const shortTime = (s?: string) => (s ? s.slice(5, 16) : "")
export const shortId = (id: string) => id.split("_").pop() ?? id
