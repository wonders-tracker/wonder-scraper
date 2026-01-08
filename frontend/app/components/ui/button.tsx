import * as React from "react"
import { cn } from "@/lib/utils"
import { Loader2 } from "lucide-react"

// Button variants using cva-style approach
const buttonVariants = {
  variant: {
    primary: "bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm",
    secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80 shadow-sm",
    destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90 shadow-sm",
    outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground shadow-sm",
    ghost: "hover:bg-accent hover:text-accent-foreground",
    link: "text-primary underline-offset-4 hover:underline",
    success: "bg-success text-success-foreground hover:bg-success/90 shadow-sm",
  },
  size: {
    xs: "h-7 px-2 text-xs rounded",
    sm: "h-8 px-3 text-xs rounded-md",
    md: "h-9 px-4 text-sm rounded-md",
    lg: "h-10 px-6 text-sm rounded-md",
    xl: "h-11 px-8 text-base rounded-lg",
    icon: "h-9 w-9 rounded-md",
    "icon-sm": "h-7 w-7 rounded",
    "icon-lg": "h-10 w-10 rounded-md",
  },
} as const

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof buttonVariants.variant
  size?: keyof typeof buttonVariants.size
  loading?: boolean
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "primary",
      size = "md",
      loading = false,
      disabled,
      leftIcon,
      rightIcon,
      children,
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || loading

    return (
      <button
        className={cn(
          // Base styles
          "inline-flex items-center justify-center gap-2 font-medium transition-colors",
          // Focus styles (accessible)
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          // Disabled styles
          "disabled:pointer-events-none disabled:opacity-50",
          // Motion preference
          "motion-reduce:transition-none",
          // Variant and size
          buttonVariants.variant[variant],
          buttonVariants.size[size],
          className
        )}
        ref={ref}
        disabled={isDisabled}
        aria-disabled={isDisabled}
        {...props}
      >
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        ) : leftIcon ? (
          <span className="shrink-0" aria-hidden="true">{leftIcon}</span>
        ) : null}
        {children}
        {rightIcon && !loading && (
          <span className="shrink-0" aria-hidden="true">{rightIcon}</span>
        )}
      </button>
    )
  }
)

Button.displayName = "Button"

// Icon button wrapper for accessibility
export interface IconButtonProps extends Omit<ButtonProps, "children" | "leftIcon" | "rightIcon"> {
  icon: React.ReactNode
  "aria-label": string
}

const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ icon, size = "icon", className, ...props }, ref) => {
    return (
      <Button
        ref={ref}
        size={size}
        className={cn("p-0", className)}
        {...props}
      >
        <span aria-hidden="true">{icon}</span>
      </Button>
    )
  }
)

IconButton.displayName = "IconButton"

export { Button, IconButton, buttonVariants }
