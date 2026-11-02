import * as React from "react"
import { cn } from "cn"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-12 w-full min-w-0 rounded-xl border border-input/70 bg-background px-4 text-[17px] transition-[border-color,box-shadow] outline-none placeholder:text-faint disabled:cursor-not-allowed disabled:bg-alt disabled:text-muted-foreground",
        "focus-visible:border-primary focus-visible:ring-[4px] focus-visible:ring-primary/20",
        "aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40",
        className
      )}
      {...props}
    />
  )
}

export { Input }
