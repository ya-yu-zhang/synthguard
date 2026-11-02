import { useCallback, useState, type ReactNode } from "react"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

type Opts = { title: string; body: ReactNode; ok?: string; cancel?: string; danger?: boolean }

/** `const [dialog, confirm] = useConfirm()`; render `dialog`, then `if (await confirm({...}))`. */
export function useConfirm() {
  const [opts, setOpts] = useState<(Opts & { resolve: (v: boolean) => void }) | null>(null)
  const confirm = useCallback((o: Opts) => new Promise<boolean>((resolve) => setOpts({ ...o, resolve })), [])
  const close = (v: boolean) => {
    opts?.resolve(v)
    setOpts(null)
  }
  const dialog = (
    <AlertDialog open={!!opts} onOpenChange={(open) => !open && close(false)}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{opts?.title}</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="text-[15px] leading-relaxed">{opts?.body}</div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{opts?.cancel ?? "再想想"}</AlertDialogCancel>
          <AlertDialogAction variant={opts?.danger ? "destructive" : "default"} onClick={() => close(true)}>
            {opts?.ok ?? "确定"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
  return [dialog, confirm] as const
}
