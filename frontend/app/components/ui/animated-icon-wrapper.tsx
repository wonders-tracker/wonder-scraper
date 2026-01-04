"use client"

import { useRef, cloneElement, ReactElement, HTMLAttributes } from 'react'

interface AnimatedIconHandle {
  startAnimation: () => void
  stopAnimation: () => void
}

interface AnimatedIconWrapperProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactElement
}

/**
 * Wrapper that triggers animated icon animations when the wrapper (not just the icon) is hovered.
 * Use this to wrap buttons/links that contain animated icons.
 *
 * Usage:
 * <AnimatedIconWrapper className="p-2 hover:bg-muted">
 *   <SearchIcon size={16} />
 * </AnimatedIconWrapper>
 */
export function AnimatedIconWrapper({ children, className, ...props }: AnimatedIconWrapperProps) {
  const iconRef = useRef<AnimatedIconHandle>(null)

  return (
    <div
      className={className}
      onMouseEnter={() => iconRef.current?.startAnimation()}
      onMouseLeave={() => iconRef.current?.stopAnimation()}
      {...props}
    >
      {cloneElement(children, { ref: iconRef })}
    </div>
  )
}
