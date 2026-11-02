import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"

/** GET a JSON resource; refetches when `path` or `epoch` changes. Keeps old data while reloading. */
export function useResource<T>(path: string | null, epoch = 0) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const load = useCallback(async () => {
    if (!path) return
    setLoading(true)
    try {
      setData(await api<T>(path))
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [path])
  useEffect(() => {
    void load()
  }, [load, epoch])
  return { data, error, loading, reload: load, setData }
}
