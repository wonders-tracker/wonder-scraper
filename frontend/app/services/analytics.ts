/**
 * Analytics Service
 *
 * Uses Vercel Analytics for custom event tracking.
 * Falls back gracefully when analytics is unavailable.
 *
 * Usage:
 *   import { analytics } from '~/services/analytics'
 *   analytics.trackSignup('email')
 *   analytics.trackLoginPageView()
 *
 * Vercel Analytics Constraints:
 * - Event names: max 255 characters
 * - Property keys: max 255 characters
 * - Property values: strings, numbers, booleans only (no nested objects)
 * - Requires Pro/Enterprise plan for custom events
 */

import { track as vercelTrack } from '@vercel/analytics'

// Type for event properties (Vercel Analytics constraints)
type EventProperties = Record<string, string | number | boolean | undefined>

// Vercel Analytics allowed property values (no undefined)
type VercelPropertyValues = string | number | boolean | null

/**
 * Core tracking function - wraps Vercel Analytics track()
 * Safely handles SSR and missing analytics
 */
function track(eventName: string, params?: EventProperties) {
  if (typeof window === 'undefined') return

  try {
    // Truncate event name to 255 chars (Vercel limit)
    const safeEventName = eventName.slice(0, 255)

    // Clean params: remove undefined values and truncate strings
    const safeParams: Record<string, VercelPropertyValues> | undefined = params
      ? Object.fromEntries(
          Object.entries(params)
            .filter((entry): entry is [string, string | number | boolean] => entry[1] !== undefined)
            .map(([k, v]) => [
              k.slice(0, 255),
              typeof v === 'string' ? v.slice(0, 255) : v,
            ])
        )
      : undefined

    vercelTrack(safeEventName, safeParams)
  } catch (error) {
    // Silently fail - analytics shouldn't break the app
    console.debug('[Analytics] Error tracking event:', error)
  }
}

// ============================================
// Custom Event Definitions
// ============================================

/**
 * Event: User Signup
 * Triggered when a user successfully creates an account
 */
function trackSignup(method: 'email' | 'discord' = 'email') {
  track('sign_up', { method })
}

/**
 * Event: Login Page View
 * Triggered when a user visits the login page
 */
function trackLoginPageView() {
  track('login_page_view')
}

/**
 * Event: Signup Page View
 * Triggered when a user visits the signup page
 */
function trackSignupPageView() {
  track('signup_page_view')
}

/**
 * Event: Discord Signup Initiated
 * Triggered when a user starts the Discord OAuth flow from signup page
 */
function trackDiscordSignupInitiated() {
  track('discord_signup_initiated')
}

/**
 * Event: Profile Access
 * Triggered when a user accesses their profile page
 */
function trackProfileAccess() {
  track('profile_access')
}

/**
 * Event: Portfolio Access
 * Triggered when a user accesses their portfolio page
 */
function trackPortfolioAccess() {
  track('portfolio_access')
}

/**
 * Event: Card Listing View
 * Triggered when a user views a card's detail page
 */
function trackCardView(cardId: string | number, cardName?: string) {
  track('view_item', {
    card_id: String(cardId),
    card_name: cardName,
  })
}

/**
 * Event: Multiple Listings Viewed
 * Triggered when a user has viewed N+ card listings in a session
 */
function trackMultipleListingsViewed(count: number) {
  track('multiple_listings_viewed', { listings_count: count })
}

/**
 * Event: Add to Portfolio
 * Triggered when a user adds a card to their portfolio
 */
function trackAddToPortfolio(cardId: string | number, cardName?: string) {
  track('add_to_portfolio', {
    card_id: String(cardId),
    card_name: cardName,
  })
}

/**
 * Event: Search
 * Triggered when a user performs a search
 */
function trackSearch(searchTerm: string) {
  track('search', { search_term: searchTerm })
}

/**
 * Event: Filter Applied
 * Triggered when a user applies a filter
 * Filter types: set, condition, printing, product_type, card_type, color, rarity, time_period
 */
function trackFilterApplied(filterType: string, filterValue: string) {
  track('filter_applied', {
    filter_type: filterType,
    filter_value: filterValue,
  })
}

/**
 * Event: Filter Removed
 * Triggered when a user removes a single filter (e.g., clicking X on a filter chip)
 */
function trackFilterRemoved(filterType: string, filterValue: string) {
  track('filter_removed', {
    filter_type: filterType,
    filter_value: filterValue,
  })
}

/**
 * Event: Filters Cleared
 * Triggered when a user clears all filters at once
 */
function trackFiltersCleared(filterCount: number) {
  track('filters_cleared', { filter_count: filterCount })
}

/**
 * Event: External Link Click
 * Triggered when a user clicks an external link (e.g., eBay listing)
 */
function trackExternalLinkClick(
  platform: string,
  cardId?: string | number,
  listingTitle?: string
) {
  track('external_link_click', {
    platform,
    card_id: cardId ? String(cardId) : undefined,
    listing_title: listingTitle,
  })
}

/**
 * Event: Chart Interaction
 * Triggered when a user interacts with a chart (time range, chart type)
 */
function trackChartInteraction(
  interactionType: 'time_range' | 'chart_type',
  value: string
) {
  track('chart_interaction', {
    interaction_type: interactionType,
    value,
  })
}

/**
 * Event: Market Page View
 * Triggered when a user views the market analysis page
 */
function trackMarketPageView() {
  track('market_page_view')
}

/**
 * Event: Welcome Page View
 * Triggered when a user views the welcome/profile completion page
 */
function trackWelcomePageView() {
  track('welcome_page_view')
}

/**
 * Event: Profile Completed
 * Triggered when a user completes their profile on the welcome page
 */
function trackProfileCompleted(hasUsername: boolean, hasDiscord: boolean) {
  track('profile_completed', {
    has_username: hasUsername,
    has_discord: hasDiscord,
  })
}

/**
 * Event: Profile Skipped
 * Triggered when a user skips profile completion on the welcome page
 */
function trackProfileSkipped() {
  track('profile_skipped')
}

/**
 * Event: Upgrade Page View
 * Triggered when a user views the upgrade/upsell page
 */
function trackUpgradePageView() {
  track('upgrade_page_view')
}

/**
 * Event: Upgrade Initiated
 * Triggered when a user clicks the upgrade button
 */
function trackUpgradeInitiated() {
  track('upgrade_initiated')
}

/**
 * Event: Upgrade Skipped
 * Triggered when a user continues as free from the upgrade page
 */
function trackUpgradeSkipped() {
  track('upgrade_skipped')
}

/**
 * Event: Discord Login Initiated
 * Triggered when a user starts the Discord OAuth flow
 */
function trackDiscordLoginInitiated() {
  track('discord_login_initiated')
}

/**
 * Event: Login Success
 * Triggered when a user successfully logs in
 */
function trackLogin(method: 'email' | 'discord' = 'email') {
  track('login', { method })
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
  trackFilterRemoved,
  trackFiltersCleared,

  // Market Events
  trackMarketPageView,
  trackChartInteraction,

  // Utility: Custom event
  custom: (eventName: string, params?: EventProperties) =>
    track(eventName, params),
}

export default analytics
