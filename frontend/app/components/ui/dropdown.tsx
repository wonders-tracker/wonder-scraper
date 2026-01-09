import * as React from "react"
import { Check, ChevronDown, Search, X } from "lucide-react"
import { cn } from "@/lib/utils"

// Types
export interface DropdownOption {
  value: string
  label: string
  disabled?: boolean
  icon?: React.ReactNode
  description?: string
  group?: string
}

interface DropdownContextValue {
  value: string | string[]
  onValueChange: (value: string | string[]) => void
  open: boolean
  setOpen: (open: boolean) => void
  multiple?: boolean
  searchable?: boolean
  searchQuery: string
  setSearchQuery: (query: string) => void
  highlightedIndex: number
  setHighlightedIndex: (index: number) => void
  options: DropdownOption[]
  filteredOptions: DropdownOption[]
  triggerRef: React.RefObject<HTMLButtonElement>
}

const DropdownContext = React.createContext<DropdownContextValue | null>(null)

function useDropdownContext() {
  const context = React.useContext(DropdownContext)
  if (!context) throw new Error("Dropdown components must be used within a Dropdown")
  return context
}

// Main Dropdown component
interface DropdownProps {
  value: string | string[]
  onValueChange: (value: string | string[]) => void
  children: React.ReactNode
  multiple?: boolean
  searchable?: boolean
  options?: DropdownOption[]
  className?: string
}

export function Dropdown({
  value,
  onValueChange,
  children,
  multiple = false,
  searchable = false,
  options = [],
  className,
}: DropdownProps) {
  const [open, setOpen] = React.useState(false)
  const [searchQuery, setSearchQuery] = React.useState("")
  const [highlightedIndex, setHighlightedIndex] = React.useState(0)
  const containerRef = React.useRef<HTMLDivElement>(null)
  const triggerRef = React.useRef<HTMLButtonElement>(null)

  // Filter options based on search query
  const filteredOptions = React.useMemo(() => {
    if (!searchQuery) return options
    const query = searchQuery.toLowerCase()
    return options.filter(
      (opt) =>
        opt.label.toLowerCase().includes(query) ||
        opt.value.toLowerCase().includes(query) ||
        opt.description?.toLowerCase().includes(query)
    )
  }, [options, searchQuery])

  // Reset search when dropdown closes
  React.useEffect(() => {
    if (!open) {
      setSearchQuery("")
      setHighlightedIndex(0)
    }
  }, [open])

  // Close on outside click
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        // Check if click is in the portal
        const portal = document.getElementById("dropdown-portal")
        if (portal && portal.contains(event.target as Node)) return
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  // Close on escape
  React.useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false)
    }
    if (open) {
      document.addEventListener("keydown", handleEscape)
      return () => document.removeEventListener("keydown", handleEscape)
    }
  }, [open])

  return (
    <DropdownContext.Provider
      value={{
        value,
        onValueChange,
        open,
        setOpen,
        multiple,
        searchable,
        searchQuery,
        setSearchQuery,
        highlightedIndex,
        setHighlightedIndex,
        options,
        filteredOptions,
        triggerRef,
      }}
    >
      <div className={cn("relative inline-block", className)} ref={containerRef}>
        {children}
      </div>
    </DropdownContext.Provider>
  )
}

// Trigger button
interface DropdownTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  placeholder?: string
  showClear?: boolean
  size?: "sm" | "md" | "lg"
}

export function DropdownTrigger({
  children,
  className,
  placeholder = "Select...",
  showClear = false,
  size = "md",
  ...props
}: DropdownTriggerProps) {
  const { value, onValueChange, open, setOpen, multiple, options, triggerRef } = useDropdownContext()

  const displayValue = React.useMemo(() => {
    if (multiple && Array.isArray(value)) {
      if (value.length === 0) return null
      if (value.length === 1) {
        const opt = options.find((o) => o.value === value[0])
        return opt?.label || value[0]
      }
      return `${value.length} selected`
    }
    const opt = options.find((o) => o.value === value)
    return opt?.label || (value as string) || null
  }, [value, multiple, options])

  const hasValue = multiple ? (value as string[]).length > 0 : !!value

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation()
    onValueChange(multiple ? [] : "")
  }

  const sizeClasses = {
    sm: "h-7 px-2 text-xs",
    md: "h-9 px-3 text-sm",
    lg: "h-11 px-4 text-base",
  }

  return (
    <button
      ref={triggerRef}
      type="button"
      className={cn(
        "flex w-full items-center justify-between gap-2 rounded-md border border-input bg-background shadow-sm ring-offset-background transition-colors",
        "hover:bg-accent/50 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
        sizeClasses[size],
        open && "ring-2 ring-ring ring-offset-2",
        className
      )}
      onClick={() => setOpen(!open)}
      aria-expanded={open}
      aria-haspopup="listbox"
      {...props}
    >
      <span className={cn("truncate", !displayValue && "text-muted-foreground")}>
        {children || displayValue || placeholder}
      </span>
      <div className="flex items-center gap-1 shrink-0">
        {showClear && hasValue && (
          <span
            role="button"
            tabIndex={-1}
            className="rounded-full p-0.5 hover:bg-muted"
            onClick={handleClear}
          >
            <X className="h-3 w-3 opacity-50 hover:opacity-100" />
          </span>
        )}
        <ChevronDown
          className={cn("h-4 w-4 opacity-50 transition-transform duration-200", open && "rotate-180")}
        />
      </div>
    </button>
  )
}

// Content container (absolute positioned within parent - avoids portal positioning issues)
interface DropdownContentProps {
  children?: React.ReactNode
  className?: string
  align?: "start" | "center" | "end"
  sideOffset?: number
  maxHeight?: number
}

export function DropdownContent({
  children,
  className,
  align = "start",
  sideOffset = 4,
  maxHeight = 300,
}: DropdownContentProps) {
  const { open, setOpen, searchable, searchQuery, setSearchQuery, filteredOptions, highlightedIndex, setHighlightedIndex, value, onValueChange, multiple } =
    useDropdownContext()
  const contentRef = React.useRef<HTMLDivElement>(null)
  const searchInputRef = React.useRef<HTMLInputElement>(null)

  // Focus search input when opened
  React.useEffect(() => {
    if (open && searchable && searchInputRef.current) {
      setTimeout(() => searchInputRef.current?.focus(), 0)
    }
  }, [open, searchable])

  // Keyboard navigation
  React.useEffect(() => {
    if (!open) return

    const handleKeyDown = (e: KeyboardEvent) => {
      const enabledOptions = filteredOptions.filter((o) => !o.disabled)

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault()
          setHighlightedIndex((highlightedIndex + 1) % enabledOptions.length)
          break
        case "ArrowUp":
          e.preventDefault()
          setHighlightedIndex((highlightedIndex - 1 + enabledOptions.length) % enabledOptions.length)
          break
        case "Enter":
          e.preventDefault()
          if (enabledOptions[highlightedIndex]) {
            const opt = enabledOptions[highlightedIndex]
            if (multiple) {
              const currentValues = value as string[]
              const newValues = currentValues.includes(opt.value)
                ? currentValues.filter((v) => v !== opt.value)
                : [...currentValues, opt.value]
              onValueChange(newValues)
            } else {
              onValueChange(opt.value)
              setOpen(false)
            }
          }
          break
        case "Home":
          e.preventDefault()
          setHighlightedIndex(0)
          break
        case "End":
          e.preventDefault()
          setHighlightedIndex(enabledOptions.length - 1)
          break
      }
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [open, filteredOptions, highlightedIndex, setHighlightedIndex, value, onValueChange, multiple, setOpen])

  if (!open) return null

  // Alignment classes for absolute positioning
  const alignClass = align === "end" ? "right-0" : align === "center" ? "left-1/2 -translate-x-1/2" : "left-0"

  return (
    <div
      ref={contentRef}
      className={cn(
        "absolute z-[9999] min-w-[8rem] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-lg",
        "animate-in fade-in-0 zoom-in-95 duration-150 slide-in-from-top-2",
        alignClass,
        className
      )}
      style={{
        top: `calc(100% + ${sideOffset}px)`,
        minWidth: "100%",
      }}
      role="listbox"
    >
      {searchable && (
        <div className="flex items-center border-b px-3 py-2">
          <Search className="h-4 w-4 shrink-0 opacity-50" />
          <input
            ref={searchInputRef}
            type="text"
            className="flex-1 bg-transparent px-2 py-1 text-sm outline-none placeholder:text-muted-foreground"
            placeholder="Search..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value)
              setHighlightedIndex(0)
            }}
          />
          {searchQuery && (
            <button
              type="button"
              className="rounded-full p-0.5 hover:bg-muted"
              onClick={() => setSearchQuery("")}
            >
              <X className="h-3 w-3 opacity-50" />
            </button>
          )}
        </div>
      )}
      <div className="p-1 overflow-y-auto" style={{ maxHeight }}>
        {children || (
          filteredOptions.length === 0 ? (
            <div className="py-6 text-center text-sm text-muted-foreground">No results found</div>
          ) : (
            <DropdownItems />
          )
        )}
      </div>
    </div>
  )
}

// Auto-render items from options prop
function DropdownItems() {
  const { filteredOptions } = useDropdownContext()

  // Group options by group property
  const grouped = React.useMemo(() => {
    const groups = new Map<string | undefined, DropdownOption[]>()
    filteredOptions.forEach((opt) => {
      const group = opt.group
      if (!groups.has(group)) groups.set(group, [])
      groups.get(group)!.push(opt)
    })
    return groups
  }, [filteredOptions])

  return (
    <>
      {Array.from(grouped.entries()).map(([group, options], groupIndex) => (
        <React.Fragment key={group || "ungrouped"}>
          {group && (
            <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              {group}
            </div>
          )}
          {options.map((option, index) => (
            <DropdownItem
              key={option.value}
              value={option.value}
              disabled={option.disabled}
              icon={option.icon}
              description={option.description}
              index={groupIndex * 100 + index}
            >
              {option.label}
            </DropdownItem>
          ))}
          {groupIndex < grouped.size - 1 && <DropdownSeparator />}
        </React.Fragment>
      ))}
    </>
  )
}

// Individual item
interface DropdownItemProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "children"> {
  value: string
  children: React.ReactNode
  disabled?: boolean
  icon?: React.ReactNode
  description?: string
  index?: number
}

export function DropdownItem({
  value: itemValue,
  children,
  className,
  disabled,
  icon,
  description,
  index = 0,
  ...props
}: DropdownItemProps) {
  const { value, onValueChange, setOpen, multiple, highlightedIndex } = useDropdownContext()

  const isSelected = multiple
    ? (value as string[]).includes(itemValue)
    : value === itemValue

  const handleSelect = () => {
    if (disabled) return
    if (multiple) {
      const currentValues = value as string[]
      const newValues = currentValues.includes(itemValue)
        ? currentValues.filter((v) => v !== itemValue)
        : [...currentValues, itemValue]
      onValueChange(newValues)
    } else {
      onValueChange(itemValue)
      setOpen(false)
    }
  }

  return (
    <div
      role="option"
      aria-selected={isSelected}
      aria-disabled={disabled}
      className={cn(
        "relative flex items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none cursor-pointer select-none",
        "transition-colors duration-75",
        isSelected && "bg-accent/50",
        highlightedIndex === index && "bg-accent",
        disabled && "pointer-events-none opacity-50",
        !disabled && "hover:bg-accent",
        className
      )}
      onClick={handleSelect}
      {...props}
    >
      {multiple && (
        <div
          className={cn(
            "flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border",
            isSelected ? "bg-primary border-primary" : "border-input"
          )}
        >
          {isSelected && <Check className="h-3 w-3 text-primary-foreground" />}
        </div>
      )}
      {icon && <span className="shrink-0">{icon}</span>}
      <div className="flex-1 min-w-0">
        <div className="truncate">{children}</div>
        {description && (
          <div className="text-xs text-muted-foreground truncate">{description}</div>
        )}
      </div>
      {!multiple && isSelected && <Check className="h-4 w-4 shrink-0 text-primary" />}
    </div>
  )
}

// Group header
interface DropdownGroupProps {
  children: React.ReactNode
  label?: string
}

export function DropdownGroup({ children, label }: DropdownGroupProps) {
  return (
    <div role="group">
      {label && (
        <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          {label}
        </div>
      )}
      {children}
    </div>
  )
}

// Separator
export function DropdownSeparator({ className }: { className?: string }) {
  return <div className={cn("-mx-1 my-1 h-px bg-border", className)} />
}

// Label for trigger
export function DropdownLabel({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <span className={cn("text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1 block", className)}>
      {children}
    </span>
  )
}

// Simple dropdown wrapper for common use cases
interface SimpleDropdownProps {
  value: string
  onChange: (value: string) => void
  options: Array<{ value: string; label: string; disabled?: boolean; count?: number }>
  placeholder?: string
  className?: string
  triggerClassName?: string
  size?: "sm" | "md" | "lg"
  searchable?: boolean
  showClear?: boolean
  disabled?: boolean
  /** Accessible label for screen readers */
  "aria-label"?: string
}

export function SimpleDropdown({
  value,
  onChange,
  options,
  placeholder = "Select...",
  className,
  triggerClassName,
  size = "md",
  searchable = false,
  showClear = false,
  disabled = false,
  "aria-label": ariaLabel,
}: SimpleDropdownProps) {
  const dropdownOptions: DropdownOption[] = options.map((o) => ({
    value: o.value,
    // Include count in label if provided
    label: o.count !== undefined ? `${o.label} (${o.count})` : o.label,
    disabled: o.disabled,
  }))

  return (
    <Dropdown
      value={value}
      onValueChange={(v) => onChange(v as string)}
      options={dropdownOptions}
      searchable={searchable}
      className={className}
    >
      <DropdownTrigger
        placeholder={placeholder}
        size={size}
        showClear={showClear}
        disabled={disabled}
        className={triggerClassName}
        aria-label={ariaLabel}
      />
      <DropdownContent />
    </Dropdown>
  )
}

export default Dropdown
