import * as React from "react"
import { cn } from "@/lib/utils"
import { Loader2 } from "lucide-react"

/**
 * Button Component - Shared button primitive for consistent styling
 *
 * Usage:
 * <Button>Default</Button>
 * <Button variant="outline" size="sm">Small Outline</Button>
 * <Button variant="discord" leftIcon={<DiscordIcon />}>Continue with Discord</Button>
 * <Button variant="ghost" size="icon" aria-label="Close"><X /></Button>
 * <IconButton icon={<Plus />} aria-label="Add item" />
 */

// Brand colors as constants (extracted from hardcoded values)
export const BRAND_COLORS = {
  discord: {
    primary: '#5865F2',
    hover: '#4752C4',
  },
  ebay: {
    primary: '#e53238',
  },
} as const

// Button variants - comprehensive set covering all use cases
const buttonVariants = {
  variant: {
    // Primary actions
    primary: "bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm",

    // Secondary actions
    secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80 shadow-sm",

    // Destructive/danger actions
    destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90 shadow-sm",

    // Outlined buttons
    outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground shadow-sm",

    // Subtle outline (pagination, filters)
    "outline-subtle": "border border-border bg-background hover:bg-muted/50 text-foreground",

    // Ghost buttons (minimal visual weight)
    ghost: "hover:bg-accent hover:text-accent-foreground",

    // Link style
    link: "text-primary underline-offset-4 hover:underline",

    // Success actions
    success: "bg-success text-success-foreground hover:bg-success/90 shadow-sm",

    // Brand mint green
    brand: "bg-brand-500 text-white hover:bg-brand-600 shadow-sm",
    "brand-soft": "bg-brand-500/10 text-brand-400 hover:bg-brand-500/20 border border-brand-500/20",

    // Discord OAuth (hardcoded because Tailwind needs static class names)
    discord: "bg-[#5865F2] text-white hover:bg-[#4752C4] shadow-sm focus-visible:outline-[#5865F2]",

    // Soft/muted variants for tags and toggles
    soft: "bg-muted text-muted-foreground hover:bg-muted/80",
    "soft-primary": "bg-primary/10 text-primary hover:bg-primary/20",

    // Toggle button states (for tab-like buttons)
    "toggle-active": "bg-primary text-primary-foreground",
    "toggle-inactive": "bg-background text-muted-foreground hover:bg-muted/50 hover:text-foreground border border-border",
  },
  size: {
    xs: "h-7 px-2 text-xs rounded gap-1",
    sm: "h-8 px-3 text-xs rounded-md gap-1.5",
    md: "h-9 px-4 text-sm rounded-md gap-2",
    lg: "h-10 px-6 text-sm rounded-md gap-2",
    xl: "h-11 px-8 text-base rounded-lg gap-2",
    // Icon-only buttons
    icon: "h-9 w-9 rounded-md p-0",
    "icon-xs": "h-6 w-6 rounded p-0",
    "icon-sm": "h-7 w-7 rounded p-0",
    "icon-lg": "h-10 w-10 rounded-md p-0",
    "icon-xl": "h-12 w-12 rounded-lg p-0",
  },
} as const

// Icon sizes that match button sizes
const iconSizeMap = {
  xs: "h-3 w-3",
  sm: "h-3.5 w-3.5",
  md: "h-4 w-4",
  lg: "h-4 w-4",
  xl: "h-5 w-5",
  icon: "h-4 w-4",
  "icon-xs": "h-3 w-3",
  "icon-sm": "h-3.5 w-3.5",
  "icon-lg": "h-5 w-5",
  "icon-xl": "h-6 w-6",
} as const

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual style variant */
  variant?: keyof typeof buttonVariants.variant
  /** Size preset */
  size?: keyof typeof buttonVariants.size
  /** Show loading spinner and disable */
  loading?: boolean
  /** Icon to show before children */
  leftIcon?: React.ReactNode
  /** Icon to show after children */
  rightIcon?: React.ReactNode
  /** Make button full width */
  fullWidth?: boolean
  /** For toggle buttons - indicates pressed state */
  pressed?: boolean
  /** Render as child component (for composition with Link, etc.) */
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
      fullWidth = false,
      pressed,
      children,
      type = "button",
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || loading
    const iconSize = iconSizeMap[size] || iconSizeMap.md

    return (
      <button
        type={type}
        className={cn(
          // Base styles
          "inline-flex items-center justify-center font-medium transition-colors",
          // Focus styles (accessible)
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          // Disabled styles
          "disabled:pointer-events-none disabled:opacity-50",
          // Motion preference
          "motion-reduce:transition-none",
          // Variant and size
          buttonVariants.variant[variant],
          buttonVariants.size[size],
          // Full width
          fullWidth && "w-full",
          className
        )}
        ref={ref}
        disabled={isDisabled}
        aria-disabled={isDisabled}
        aria-pressed={pressed}
        {...props}
      >
        {loading ? (
          <Loader2 className={cn(iconSize, "animate-spin")} aria-hidden="true" />
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

// Icon button wrapper for accessibility - requires aria-label
export interface IconButtonProps extends Omit<ButtonProps, "children" | "leftIcon" | "rightIcon"> {
  /** The icon to display */
  icon: React.ReactNode
  /** Required accessible label */
  "aria-label": string
}

const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ icon, size = "icon", variant = "ghost", className, ...props }, ref) => {
    const iconSize = iconSizeMap[size] || iconSizeMap.icon

    return (
      <Button
        ref={ref}
        size={size}
        variant={variant}
        className={className}
        {...props}
      >
        <span className={iconSize} aria-hidden="true">{icon}</span>
      </Button>
    )
  }
)

IconButton.displayName = "IconButton"

// Close/Remove button - common pattern for dismissible items
export interface CloseButtonProps extends Omit<ButtonProps, "children" | "leftIcon" | "rightIcon"> {
  /** Accessible label, defaults to "Close" */
  "aria-label"?: string
}

const CloseButton = React.forwardRef<HTMLButtonElement, CloseButtonProps>(
  ({ className, "aria-label": ariaLabel = "Close", size = "icon-xs", ...props }, ref) => {
    return (
      <Button
        ref={ref}
        variant="ghost"
        size={size}
        aria-label={ariaLabel}
        className={cn("hover:bg-muted rounded-full", className)}
        {...props}
      >
        <span aria-hidden="true">×</span>
      </Button>
    )
  }
)

CloseButton.displayName = "CloseButton"

// Discord Icon component (extracted for reuse)
export function DiscordIcon({ className }: { className?: string }) {
  return (
    <svg
      className={cn("w-5 h-5", className)}
      fill="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037 3.903 3.903 0 0 0-.94 1.933 18.37 18.37 0 0 0-4.814 0 3.902 3.902 0 0 0-.94-1.933.074.074 0 0 0-.079-.037 19.79 19.79 0 0 0-4.885 1.515.074.074 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.118.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.074.074 0 0 0-.032-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.418 2.157-2.418 1.21 0 2.176 1.085 2.157 2.419 0 1.334-.956 2.419-2.157 2.419zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.418 2.157-2.418 1.21 0 2.176 1.085 2.157 2.419 0 1.334-.946 2.419-2.157 2.419z" />
    </svg>
  )
}

// Helper to get icon size class for a button size
export function getIconSize(buttonSize: keyof typeof buttonVariants.size): string {
  return iconSizeMap[buttonSize] || iconSizeMap.md
}

export { Button, IconButton, CloseButton, buttonVariants, iconSizeMap }
