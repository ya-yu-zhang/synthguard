import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Slot } from "radix-ui"

const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-1.5 rounded-full font-normal whitespace-nowrap transition-[background-color,color,box-shadow,transform] outline-none focus-visible:ring-[4px] focus-visible:ring-ring/35 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-40 aria-invalid:ring-destructive/20 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary-hover",
        destructive: "bg-destructive text-white hover:bg-destructive/90",
        outline: "border border-foreground/20 bg-transparent text-foreground hover:bg-foreground/[0.04]",
        secondary: "bg-foreground/[0.06] text-foreground hover:bg-foreground/10",
        ghost: "text-foreground hover:bg-foreground/[0.05]",
        link: "rounded-none px-0 text-link hover:underline underline-offset-4",
      },
      size: {
        default: "h-10 px-5 text-[15px]",
        xs: "h-6 px-2.5 text-xs",
        sm: "h-7 px-3 text-xs",
        lg: "h-12 px-7 text-[17px]",
        icon: "size-10",
        "icon-xs": "size-6 [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-8",
        "icon-lg": "size-12",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
