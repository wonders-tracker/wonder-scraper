/**
 * Hybrid Analytics Service (Google Analytics + Vercel Analytics + Backend)
 *
 * Extensible analytics factory for tracking custom events.
 * Sends events to GA, Vercel Analytics, and our backend for redundancy.
 *
 * GA Measurement ID: G-28SPPTBF79
 *
 * Usage:
 *   import { analytics } from '~/services/analytics'
 *   analytics.trackSignup('email')
 *   analytics.trackLoginPageView()
 */

import { track as vercelTrack } from '@vercel/analytics'

// API base URL
const API_BASE = import.meta.env.VITE_API_URL || ''

// Declare gtag on window
declare global {
  interface Window {
    gtag: (...args: any[]) => void
    dataLayer: any[]
  }
}

// GA Measurement ID
const GA_MEASUREMENT_ID = 'G-28SPPTBF79'

/**
 * Core tracking function - sends to both GA and Vercel Analytics
 */
function track(eventName: string, params?: Record<string, any>) {
  if (typeof window === 'undefined') return

  // Send to Google Analytics
  if (window.gtag) {
    try {
      window.gtag('event', eventName, {
        ...params,
        send_to: GA_MEASUREMENT_ID,
      })
    } catch (error) {
      console.error('[Analytics:GA] Error tracking event:', error)
    }
  }

  // Send to Vercel Analytics
  try {
    // Vercel Analytics has limitations: max 255 chars per key/value, no nested objects
    // Clean params for Vercel compatibility
    const vercelParams = params ? cleanParamsForVercel(params) : undefined
    vercelTrack(eventName, vercelParams)
  } catch (error) {
    console.error('[Analytics:Vercel] Error tracking event:', error)
  }
}

/**
 * Clean params for Vercel Analytics compatibility
 * - Removes nested objects
 * - Truncates strings > 255 chars
 * - Only allows strings, numbers, booleans, null
 */
function cleanParamsForVercel(params: Record<string, any>): Record<string, string | number | boolean | null> {
  const cleaned: Record<string, string | number | boolean | null> = {}

  for (const [key, value] of Object.entries(params)) {
    // Skip nested objects/arrays
    if (typeof value === 'object' && value !== null) continue

    // Truncate long strings
    if (typeof value === 'string') {
      cleaned[key.slice(0, 255)] = value.slice(0, 255)
    } else if (typeof value === 'number' || typeof value === 'boolean' || value === null) {
      cleaned[key.slice(0, 255)] = value
    }
  }

  return cleaned
}

// Session ID for correlating events
let sessionId: string | null = null
function getSessionId(): string {
  if (typeof window === 'undefined') return ''
  if (!sessionId) {
    sessionId = sessionStorage.getItem('wt_session_id')
    if (!sessionId) {
      sessionId = `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
      sessionStorage.setItem('wt_session_id', sessionId)
    }
  }
  return sessionId
}

/**
 * Send event to backend analytics API
 * Fire-and-forget, non-blocking
 */
function sendToBackend(eventName: string, properties?: Record<string, any>) {
  if (typeof window === 'undefined') return

  // Use navigator.sendBeacon for reliability (won't block page unload)
  const payload = JSON.stringify({
    event_name: eventName,
    properties: properties || {},
    session_id: getSessionId(),
  })

  try {
    // Try sendBeacon first (better for page unloads)
    if (navigator.sendBeacon) {
      const blob = new Blob([payload], { type: 'application/json' })
      navigator.sendBeacon(`${API_BASE}/api/v1/analytics/event`, blob)
    } else {
      // Fallback to fetch
      fetch(`${API_BASE}/api/v1/analytics/event`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
        keepalive: true,
      }).catch(() => {})
    }
  } catch {
    // Silently fail - analytics should never break the app
  }
}

/**
 * Track page views (for SPAs)
 */
function trackPageView(path: string, title?: string) {
  if (typeof window === 'undefined') return
  if (!window.gtag) return

  window.gtag('config', GA_MEASUREMENT_ID, {
    page_path: path,
    page_title: title,
  })
}

// ============================================
// Custom Event Definitions
// ============================================

/**
 * Event: User Signup
 * Triggered when a user successfully creates an account
 */
function trackSignup(method: 'email' | 'discord' = 'email') {
  const params = {
    method,
    event_category: 'engagement',
    event_label: `signup_${method}`,
  }
  track('sign_up', params)
  sendToBackend('sign_up', params)
}

/**
 * Event: Login Page View
 * Triggered when a user visits the login page
 */
function trackLoginPageView() {
  track('login_page_view', {
    event_category: 'engagement',
    event_label: 'viewed_login_page',
  })
}

/**
 * Event: Signup Page View
 * Triggered when a user visits the signup page
 */
function trackSignupPageView() {
  track('signup_page_view', {
    event_category: 'engagement',
    event_label: 'viewed_signup_page',
  })
}

/**
 * Event: Discord Signup Initiated
 * Triggered when a user starts the Discord OAuth flow from signup page
 */
function trackDiscordSignupInitiated() {
  track('discord_signup_initiated', {
    event_category: 'engagement',
    event_label: 'started_discord_oauth_signup',
  })
}

/**
 * Event: Profile Access
 * Triggered when a user accesses their profile page
 */
function trackProfileAccess() {
  track('profile_access', {
    event_category: 'engagement',
    event_label: 'accessed_profile',
  })
}

/**
 * Event: Portfolio Access
 * Triggered when a user accesses their portfolio page
 */
function trackPortfolioAccess() {
  track('portfolio_access', {
    event_category: 'engagement',
    event_label: 'accessed_portfolio',
  })
}

/**
 * Event: Card Listing View
 * Triggered when a user views a card's detail page
 */
function trackCardView(cardId: string | number, cardName?: string) {
  const params = {
    event_category: 'engagement',
    event_label: 'viewed_card_listing',
    card_id: cardId,
    card_name: cardName,
  }
  track('view_item', params)
  sendToBackend('card_view', params)
}

/**
 * Event: Multiple Listings Viewed
 * Triggered when a user has viewed N+ card listings in a session
 */
function trackMultipleListingsViewed(count: number) {
  track('multiple_listings_viewed', {
    event_category: 'engagement',
    event_label: `viewed_${count}_listings`,
    listings_count: count,
  })
}

/**
 * Event: Add to Portfolio
 * Triggered when a user adds a card to their portfolio
 */
function trackAddToPortfolio(cardId: string | number, cardName?: string) {
  const params = {
    event_category: 'engagement',
    event_label: 'added_to_portfolio',
    card_id: cardId,
    card_name: cardName,
  }
  track('add_to_portfolio', params)
  sendToBackend('add_to_portfolio', params)
}

/**
 * Event: Search
 * Triggered when a user performs a search
 */
function trackSearch(searchTerm: string) {
  const params = {
    search_term: searchTerm,
    event_category: 'engagement',
  }
  track('search', params)
  sendToBackend('search', params)
}

/**
 * Event: Filter Applied
 * Triggered when a user applies a filter
 */
function trackFilterApplied(filterType: string, filterValue: string) {
  track('filter_applied', {
    event_category: 'engagement',
    filter_type: filterType,
    filter_value: filterValue,
  })
}

/**
 * Event: External Link Click
 * Triggered when a user clicks an external link (e.g., eBay listing)
 */
function trackExternalLinkClick(platform: string, cardId?: string | number, listingTitle?: string) {
  const params = {
    event_category: 'conversion',
    event_label: `clicked_${platform}_listing`,
    platform,
    card_id: cardId,
    listing_title: listingTitle,
  }
  track('external_link_click', params)
  sendToBackend('external_link_click', params)
}

/**
 * Event: Chart Interaction
 * Triggered when a user interacts with a chart (time range, chart type)
 */
function trackChartInteraction(interactionType: 'time_range' | 'chart_type', value: string) {
  track('chart_interaction', {
    event_category: 'engagement',
    interaction_type: interactionType,
    value,
  })
}

/**
 * Event: Market Page View
 * Triggered when a user views the market analysis page
 */
function trackMarketPageView() {
  track('market_page_view', {
    event_category: 'engagement',
    event_label: 'viewed_market_analysis',
  })
}

/**
 * Event: Welcome Page View
 * Triggered when a user views the welcome/profile completion page
 */
function trackWelcomePageView() {
  track('welcome_page_view', {
    event_category: 'engagement',
    event_label: 'viewed_welcome_page',
  })
}

/**
 * Event: Profile Completed
 * Triggered when a user completes their profile on the welcome page
 */
function trackProfileCompleted(hasUsername: boolean, hasDiscord: boolean) {
  track('profile_completed', {
    event_category: 'engagement',
    event_label: 'completed_profile',
    has_username: hasUsername,
    has_discord: hasDiscord,
  })
}

/**
 * Event: Profile Skipped
 * Triggered when a user skips profile completion on the welcome page
 */
function trackProfileSkipped() {
  track('profile_skipped', {
    event_category: 'engagement',
    event_label: 'skipped_profile_completion',
  })
}

/**
 * Event: Upgrade Page View
 * Triggered when a user views the upgrade/upsell page
 */
function trackUpgradePageView() {
  track('upgrade_page_view', {
    event_category: 'engagement',
    event_label: 'viewed_upgrade_page',
  })
}

/**
 * Event: Upgrade Initiated
 * Triggered when a user clicks the upgrade button
 */
function trackUpgradeInitiated() {
  track('upgrade_initiated', {
    event_category: 'conversion',
    event_label: 'started_checkout',
  })
}

/**
 * Event: Upgrade Skipped
 * Triggered when a user continues as free from the upgrade page
 */
function trackUpgradeSkipped() {
  track('upgrade_skipped', {
    event_category: 'engagement',
    event_label: 'skipped_upgrade',
  })
}

/**
 * Event: Discord Login Initiated
 * Triggered when a user starts the Discord OAuth flow
 */
function trackDiscordLoginInitiated() {
  track('discord_login_initiated', {
    event_category: 'engagement',
    event_label: 'started_discord_oauth',
  })
}

/**
 * Event: Login Success
 * Triggered when a user successfully logs in
 */
function trackLogin(method: 'email' | 'discord' = 'email') {
  const params = {
    method,
    event_category: 'engagement',
    event_label: `login_${method}`,
  }
  track('login', params)
  sendToBackend('login', params)
}

// ============================================
// Session-based tracking helpers
// ============================================

const SESSION_STORAGE_KEY = 'wt_viewed_cards'
const MULTIPLE_VIEW_THRESHOLD = 3

/**
 * Track card view and check for multiple listings milestone
 */
function trackCardViewWithSession(cardId: string | number, cardName?: string) {
  // Track the individual view
  trackCardView(cardId, cardName)

  if (typeof window === 'undefined') return

  // Get or initialize session viewed cards
  let viewedCards: string[] = []
  try {
    const stored = sessionStorage.getItem(SESSION_STORAGE_KEY)
    viewedCards = stored ? JSON.parse(stored) : []
  } catch {
    viewedCards = []
  }

  // Add this card if not already viewed
  const cardIdStr = String(cardId)
  if (!viewedCards.includes(cardIdStr)) {
    viewedCards.push(cardIdStr)
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(viewedCards))

    // Check if we hit the threshold
    if (viewedCards.length === MULTIPLE_VIEW_THRESHOLD) {
      trackMultipleListingsViewed(MULTIPLE_VIEW_THRESHOLD)
    }
  }
}

// ============================================
// Analytics Factory Export
// ============================================

export const analytics = {
  // Core
  track,
  trackPageView,

  // Auth Events
  trackSignup,
  trackLogin,
  trackLoginPageView,
  trackSignupPageView,
  trackDiscordLoginInitiated,
  trackDiscordSignupInitiated,

  // User Events
  trackProfileAccess,
  trackPortfolioAccess,

  // Onboarding Events
  trackWelcomePageView,
  trackProfileCompleted,
  trackProfileSkipped,
  trackUpgradePageView,
  trackUpgradeInitiated,
  trackUpgradeSkipped,

  // Card/Listing Events
  trackCardView,
  trackCardViewWithSession,
  trackMultipleListingsViewed,
  trackAddToPortfolio,
  trackExternalLinkClick,

  // Discovery Events
  trackSearch,
  trackFilterApplied,

  // Market Events
  trackMarketPageView,
  trackChartInteraction,

  // Utility: Custom event
  custom: (eventName: string, params?: Record<string, any>) => track(eventName, params),
}

export default analytics
