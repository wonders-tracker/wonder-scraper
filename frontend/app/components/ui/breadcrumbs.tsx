/**
 * Breadcrumbs - Navigation trail component
 *
 * Shows the current location in the site hierarchy with
 * clickable links back to parent pages.
 */

import { Link } from '@tanstack/react-router'
import { cn } from '@/lib/utils'
import { ChevronRight, Home } from 'lucide-react'

export type BreadcrumbItem = {
  label: string
  href?: string
  /** Active/current page (no link) */
  current?: boolean
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[]
  /** Show home icon for first item */
  showHomeIcon?: boolean
  className?: string
}

/**
 * Breadcrumb navigation component
 */
export function Breadcrumbs({
  items,
  showHomeIcon = true,
  className,
}: BreadcrumbsProps) {
  if (items.length === 0) return null

  return (
    <nav aria-label="Breadcrumb" className={cn('mb-4', className)}>
      <ol className="flex items-center gap-1.5 text-sm flex-wrap">
        {items.map((item, index) => {
          const isFirst = index === 0
          const isLast = index === items.length - 1
          const showIcon = isFirst && showHomeIcon

          return (
            <li key={item.label} className="flex items-center gap-1.5">
              {/* Separator (except first item) */}
              {!isFirst && (
                <ChevronRight
                  className="w-3.5 h-3.5 text-muted-foreground/50 flex-shrink-0"
                  aria-hidden="true"
                />
              )}

              {/* Link or current page */}
              {item.current || isLast || !item.href ? (
                <span
                  className={cn(
                    'flex items-center gap-1.5',
                    isLast
                      ? 'text-foreground font-medium'
                      : 'text-muted-foreground'
                  )}
                  aria-current={isLast ? 'page' : undefined}
                >
                  {showIcon && (
                    <Home className="w-3.5 h-3.5" aria-hidden="true" />
                  )}
                  <span className="truncate max-w-[200px]">{item.label}</span>
                </span>
              ) : (
                <Link
                  to={item.href}
                  className={cn(
                    'flex items-center gap-1.5',
                    'text-muted-foreground hover:text-foreground transition-colors',
                    'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded'
                  )}
                >
                  {showIcon && (
                    <Home className="w-3.5 h-3.5" aria-hidden="true" />
                  )}
                  <span className="truncate max-w-[200px]">{item.label}</span>
                </Link>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
