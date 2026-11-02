// Typed client for the Python server (src/synthguard/ui_server.py). Shapes mirror its JSON.
export type JobStatus = "running" | "done" | "cancelled" | "failed"

export type Job = {
  batch: string
  operator: string
  done: number
  total: number
  errors: number
  recent: string[]
  status: JobStatus
  elapsed: number
  eta: number | null
  log: string[]
}

export type AppState = {
  host: string
  comfy_url: string
  comfy_online: boolean
  comfy_devices: string[]
  gen_profile: string
  can_config: boolean
  job: Job | null
}

export type SceneElement = { name: string; label: string; shows: string[]; weight: number }
export type Spec = {
  name: string
  title: string
  description: string
  classes: string[]
  class_labels: Record<string, string>
  elements: SceneElement[]
}
export type Rate = { sec_per_image?: number; mb_per_image?: number; from?: string }
export type Specs = { specs: Spec[]; next_batch: string; rate: Rate }

export type BatchInfo = {
  batch: string
  spec?: string
  n?: number
  seed?: number
  operator?: string
  status?: JobStatus
  images: number
  rejected: number
  cover: string | null
  size_mb: number
  started?: string
  finished?: string
  seconds?: number
  model?: string
  steps?: number
}
export type Row = {
  id: string
  file: string
  w: number
  h: number
  seed: number
  model: string
  steps: number
  prompt: string
  elements: string[]
  requested_classes: string[]
}
export type BatchDetail = { info: BatchInfo; rows: Row[]; rejected: string[] }

export type CheckStatus = "ok" | "warn" | "fail" | "skip"
export type Check = { id: string; label: string; status: CheckStatus; detail: string; fix: string }
export type Health = { checks: Check[] }

export type ConfigField = {
  key: string
  label: string
  group: "gen" | "exp"
  help: string
  value: string
  in_file: boolean
  overridden: boolean
}
export type Config = {
  fields: ConfigField[]
  profiles: string[]
  exists: boolean
  can_config: boolean
  repo: string
  krea2: Record<string, string>
}

export class ApiError extends Error {
  status: number
  errors: string[]
  constructor(message: string, status: number, errors: string[] = []) {
    super(message)
    this.status = status
    this.errors = errors
  }
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(
      path,
      body === undefined
        ? { cache: "no-store" }
        : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    )
  } catch {
    throw new ApiError("连不上 SynthGuard 服务，确认它还在运行", 0)
  }
  let data: { error?: string; errors?: string[] } = {}
  try {
    data = await res.json()
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    const errors = data.errors ?? []
    throw new ApiError(data.error || errors.join("；") || `请求失败（${res.status}）`, res.status, errors)
  }
  return data as T
}

const enc = encodeURIComponent
export const thumbUrl = (batch: string, id: string) => `/api/batches/${enc(batch)}/thumb/${id}`
export const imageUrl = (batch: string, id: string) => `/api/batches/${enc(batch)}/image/${id}`
export const downloadUrl = (batch: string) => `/api/batches/${enc(batch)}/download`
