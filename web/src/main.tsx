import { StrictMode, useEffect } from "react"
import { createRoot } from "react-dom/client"
import "./index.css"
import { AppProvider } from "@/app-context"
import { AppShell } from "@/components/app-shell"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { useRoute } from "@/lib/route"
import { EnvPage } from "@/pages/env"
import { GeneratePage } from "@/pages/generate"
import { ResultsPage } from "@/pages/results"

function App() {
  const { page, param } = useRoute()
  useEffect(() => {
    // block body on purpose: newer browsers return a Promise from scrollTo, which React
    // would then try to call as this effect's cleanup
    window.scrollTo(0, 0)
  }, [page, param])
  return (
    <AppShell page={page}>
      {page === "results" ? <ResultsPage param={param} /> : page === "env" ? <EnvPage /> : <GeneratePage />}
    </AppShell>
  )
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppProvider>
      <TooltipProvider delayDuration={300}>
        <App />
        <Toaster position="bottom-center" />
      </TooltipProvider>
    </AppProvider>
  </StrictMode>,
)
