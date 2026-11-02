import { useCallback, useEffect, useState } from "react"

export type Theme = "light" | "dark" | "system"
const KEY = "sg.theme" // raw string: index.html reads it before first paint

function read(): Theme {
  try {
    const v = localStorage.getItem(KEY)
    return v === "light" || v === "dark" ? v : "system"
  } catch {
    return "system"
  }
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(read)
  const [systemDark, setSystemDark] = useState(() => matchMedia("(prefers-color-scheme: dark)").matches)
  useEffect(() => {
    const mq = matchMedia("(prefers-color-scheme: dark)")
    const f = () => setSystemDark(mq.matches)
    mq.addEventListener("change", f)
    return () => mq.removeEventListener("change", f)
  }, [])
  const resolved: "light" | "dark" = theme === "system" ? (systemDark ? "dark" : "light") : theme
  useEffect(() => {
    document.documentElement.classList.toggle("dark", resolved === "dark")
  }, [resolved])
  const setTheme = useCallback((t: Theme) => {
    try {
      localStorage.setItem(KEY, t)
    } catch {
      /* not persisted */
    }
    setThemeState(t)
  }, [])
  return { theme, resolved, setTheme }
}
