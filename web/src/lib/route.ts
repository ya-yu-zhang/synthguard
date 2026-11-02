import { useEffect, useState } from "react"

export type Page = "generate" | "results" | "env"
const PAGES: Page[] = ["generate", "results", "env"]

/** Hash routes (#generate, #results/batch01, #env): no server-side routing needed. */
export function useRoute() {
  const [hash, setHash] = useState(() => location.hash)
  useEffect(() => {
    const onChange = () => setHash(location.hash)
    window.addEventListener("hashchange", onChange)
    return () => window.removeEventListener("hashchange", onChange)
  }, [])
  const [p, param] = hash.replace(/^#\/?/, "").split("/")
  const page = (PAGES as string[]).includes(p) ? (p as Page) : "generate"
  return { page, param: param ? decodeURIComponent(param) : undefined }
}

export const href = (page: Page, param?: string) => `#${page}${param ? "/" + encodeURIComponent(param) : ""}`
