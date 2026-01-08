import * as React from "react"
import { ErrorState } from "./ui/empty-state"

interface ErrorBoundaryProps {
  children: React.ReactNode
  fallback?: React.ReactNode
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

/**
 * Error boundary component that catches JavaScript errors in child components
 * and displays a fallback UI instead of crashing the whole app.
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log error to console in development
    console.error("ErrorBoundary caught an error:", error, errorInfo)

    // Call optional onError callback (useful for error tracking services)
    this.props.onError?.(error, errorInfo)
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      // Custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback
      }

      // Default error UI
      return (
        <div className="min-h-[200px] flex items-center justify-center p-4">
          <ErrorState
            title="Something went wrong"
            description={
              process.env.NODE_ENV === "development"
                ? this.state.error?.message
                : "An unexpected error occurred. Please try refreshing the page."
            }
            onRetry={this.handleRetry}
          />
        </div>
      )
    }

    return this.props.children
  }
}

/**
 * Hook for functional component error handling (for async errors)
 * Use this for errors in event handlers or async operations
 */
export function useErrorHandler() {
  const [error, setError] = React.useState<Error | null>(null)

  const handleError = React.useCallback((error: Error) => {
    console.error("Error caught:", error)
    setError(error)
  }, [])

  const clearError = React.useCallback(() => {
    setError(null)
  }, [])

  return { error, handleError, clearError }
}

/**
 * Route-level error boundary wrapper
 * Use this in route files to catch errors per-route
 */
export function RouteErrorBoundary({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary
      fallback={
        <div className="min-h-screen flex items-center justify-center p-4">
          <ErrorState
            title="Page Error"
            description="This page encountered an error. Try going back or refreshing."
            onRetry={() => window.location.reload()}
          />
        </div>
      }
    >
      {children}
    </ErrorBoundary>
  )
}
