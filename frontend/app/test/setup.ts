import '@testing-library/jest-dom'
import { vi, beforeEach } from 'vitest'

// Mock window.gtag
const mockGtag = vi.fn()

Object.defineProperty(window, 'gtag', {
  value: mockGtag,
  writable: true,
})

Object.defineProperty(window, 'dataLayer', {
  value: [],
  writable: true,
})

// Reset mocks before each test
beforeEach(() => {
  mockGtag.mockClear()
  sessionStorage.clear()
})

export { mockGtag }
