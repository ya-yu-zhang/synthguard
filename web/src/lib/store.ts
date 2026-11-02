// localStorage can throw (private windows, blocked storage): every access is guarded.
export const store = {
  get<T>(key: string, fallback: T): T {
    try {
      const v = localStorage.getItem("sg." + key)
      return v === null ? fallback : (JSON.parse(v) as T)
    } catch {
      return fallback
    }
  },
  set(key: string, value: unknown) {
    try {
      localStorage.setItem("sg." + key, JSON.stringify(value))
    } catch {
      /* not persisted */
    }
  },
}

// "I have looked at this image" is personal to each reviewer: kept per browser only.
export const seen = {
  get: (batch: string) => new Set(store.get<string[]>("seen." + batch, [])),
  add(batch: string, id: string) {
    const s = seen.get(batch)
    if (s.has(id)) return false
    s.add(id)
    store.set("seen." + batch, [...s])
    return true
  },
}

export async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // http:// opened from another PC is not a secure context
    const ta = document.createElement("textarea")
    ta.value = text
    ta.style.position = "fixed"
    ta.style.opacity = "0"
    document.body.append(ta)
    ta.select()
    document.execCommand("copy")
    ta.remove()
  }
}
