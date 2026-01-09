import * as React from "react"

interface UseKeyboardNavigationOptions {
  /** Callback when Enter or Space is pressed on an item */
  onSelect?: (index: number) => void
  /** Callback when an item is focused */
  onFocus?: (index: number) => void
  /** Whether navigation wraps around at edges */
  wrap?: boolean
  /** Orientation of the list */
  orientation?: "vertical" | "horizontal" | "both"
  /** Whether the component is disabled */
  disabled?: boolean
}

interface UseKeyboardNavigationReturn {
  /** Current focused index */
  focusedIndex: number
  /** Set focused index manually */
  setFocusedIndex: (index: number) => void
  /** Props to spread on the container */
  containerProps: {
    onKeyDown: (e: React.KeyboardEvent) => void
    role: string
    "aria-activedescendant"?: string
  }
  /** Get props for each item */
  getItemProps: (index: number) => {
    tabIndex: number
    "aria-selected": boolean
    onFocus: () => void
    onClick: () => void
    onKeyDown: (e: React.KeyboardEvent) => void
    id: string
  }
  /** Reset focus to first item */
  resetFocus: () => void
}

/**
 * Hook for keyboard navigation in lists, tables, and menus
 * Implements WAI-ARIA patterns for accessible navigation
 */
export function useKeyboardNavigation(
  itemCount: number,
  options: UseKeyboardNavigationOptions = {}
): UseKeyboardNavigationReturn {
  const {
    onSelect,
    onFocus,
    wrap = true,
    orientation = "vertical",
    disabled = false,
  } = options

  const [focusedIndex, setFocusedIndex] = React.useState(-1)
  const containerId = React.useId()

  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent, currentIndex?: number) => {
      if (disabled || itemCount === 0) return

      const activeIndex = currentIndex ?? focusedIndex
      let newIndex = activeIndex

      const isVertical = orientation === "vertical" || orientation === "both"
      const isHorizontal = orientation === "horizontal" || orientation === "both"

      switch (e.key) {
        case "ArrowDown":
          if (isVertical) {
            e.preventDefault()
            if (wrap) {
              newIndex = (activeIndex + 1) % itemCount
            } else {
              newIndex = Math.min(activeIndex + 1, itemCount - 1)
            }
          }
          break

        case "ArrowUp":
          if (isVertical) {
            e.preventDefault()
            if (wrap) {
              newIndex = (activeIndex - 1 + itemCount) % itemCount
            } else {
              newIndex = Math.max(activeIndex - 1, 0)
            }
          }
          break

        case "ArrowRight":
          if (isHorizontal) {
            e.preventDefault()
            if (wrap) {
              newIndex = (activeIndex + 1) % itemCount
            } else {
              newIndex = Math.min(activeIndex + 1, itemCount - 1)
            }
          }
          break

        case "ArrowLeft":
          if (isHorizontal) {
            e.preventDefault()
            if (wrap) {
              newIndex = (activeIndex - 1 + itemCount) % itemCount
            } else {
              newIndex = Math.max(activeIndex - 1, 0)
            }
          }
          break

        case "Home":
          e.preventDefault()
          newIndex = 0
          break

        case "End":
          e.preventDefault()
          newIndex = itemCount - 1
          break

        case "Enter":
        case " ":
          if (activeIndex >= 0) {
            e.preventDefault()
            onSelect?.(activeIndex)
          }
          break

        default:
          return
      }

      if (newIndex !== activeIndex && newIndex >= 0) {
        setFocusedIndex(newIndex)
        onFocus?.(newIndex)
      }
    },
    [focusedIndex, itemCount, wrap, orientation, disabled, onSelect, onFocus]
  )

  const getItemProps = React.useCallback(
    (index: number) => ({
      tabIndex: focusedIndex === index || (focusedIndex === -1 && index === 0) ? 0 : -1,
      "aria-selected": focusedIndex === index,
      onFocus: () => {
        setFocusedIndex(index)
        onFocus?.(index)
      },
      onClick: () => {
        setFocusedIndex(index)
        onSelect?.(index)
      },
      onKeyDown: (e: React.KeyboardEvent) => handleKeyDown(e, index),
      id: `${containerId}-item-${index}`,
    }),
    [focusedIndex, containerId, onFocus, onSelect, handleKeyDown]
  )

  const containerProps = React.useMemo(
    () => ({
      onKeyDown: handleKeyDown,
      role: "listbox" as const,
      "aria-activedescendant":
        focusedIndex >= 0 ? `${containerId}-item-${focusedIndex}` : undefined,
    }),
    [handleKeyDown, focusedIndex, containerId]
  )

  const resetFocus = React.useCallback(() => {
    setFocusedIndex(-1)
  }, [])

  return {
    focusedIndex,
    setFocusedIndex,
    containerProps,
    getItemProps,
    resetFocus,
  }
}

/**
 * Simplified hook for table row keyboard navigation
 */
export function useTableKeyboardNav(
  rowCount: number,
  options: {
    onRowSelect?: (index: number) => void
    disabled?: boolean
  } = {}
) {
  const { focusedIndex, getItemProps, containerProps, setFocusedIndex } = useKeyboardNavigation(
    rowCount,
    {
      onSelect: options.onRowSelect,
      orientation: "vertical",
      wrap: false,
      disabled: options.disabled,
    }
  )

  const getRowProps = React.useCallback(
    (index: number) => {
      const itemProps = getItemProps(index)
      return {
        tabIndex: itemProps.tabIndex,
        "aria-selected": itemProps["aria-selected"],
        onFocus: itemProps.onFocus,
        onClick: itemProps.onClick,
        onKeyDown: itemProps.onKeyDown,
        role: "row" as const,
        className: focusedIndex === index
          ? "ring-2 ring-inset ring-ring outline-none"
          : "focus:ring-2 focus:ring-inset focus:ring-ring focus:outline-none",
      }
    },
    [getItemProps, focusedIndex]
  )

  return {
    focusedIndex,
    setFocusedIndex,
    getRowProps,
    tableProps: {
      role: "grid" as const,
      "aria-rowcount": rowCount,
    },
  }
}
