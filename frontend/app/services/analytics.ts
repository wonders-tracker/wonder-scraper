/**
 * Google Analytics Service
 *
 * Extensible analytics factory for tracking custom events.
 * Measurement ID: G-28SPPTBF79
 *
 * Usage:
 *   import { analytics } from '~/services/analytics'
 *   analytics.trackSignup('email')
 *   analytics.trackLoginPageView()
 */

// GA types
type GtagCommand = 'event' | 'config' | 'set' | 'js'
type GtagParams = Record<string, string | number | boolean | undefined>

// Declare gtag on window
declare global {
  interface Window {
    gtag: (command: GtagCommand, action: string | Date, params?: GtagParams) => void
    dataLayer: Array<unknown>
  }
}

// GA Measurement ID
const GA_MEASUREMENT_ID = 'G-28SPPTBF79'

/**
 * Core tracking function - wraps gtag for safety
 */
function track(eventName: string, params?: GtagParams) {
  if (typeof window === 'undefined') return
  if (!window.gtag) {
    console.warn('[Analytics] gtag not loaded')
    return
  }

  try {
    window.gtag('event', eventName, {
      ...params,
      send_to: GA_MEASUREMENT_ID,
    })
  } catch (error) {
    console.error('[Analytics] Error tracking event:', error)
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
  track('sign_up', {
    method,
    event_category: 'engagement',
    event_label: `signup_${method}`,
  })
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
  track('view_item', {
    event_category: 'engagement',
    event_label: 'viewed_card_listing',
    card_id: cardId,
    card_name: cardName,
  })
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
  track('add_to_portfolio', {
    event_category: 'engagement',
    event_label: 'added_to_portfolio',
    card_id: cardId,
    card_name: cardName,
  })
}

/**
 * Event: Search
 * Triggered when a user performs a search
 */
function trackSearch(searchTerm: string) {
  track('search', {
    search_term: searchTerm,
    event_category: 'engagement',
  })
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
  track('external_link_click', {
    event_category: 'conversion',
    event_label: `clicked_${platform}_listing`,
    platform,
    card_id: cardId,
    listing_title: listingTitle,
  })
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
  track('login', {
    method,
    event_category: 'engagement',
    event_label: `login_${method}`,
  })
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
  custom: (eventName: string, params?: GtagParams) => track(eventName, params),
}

export default analytics
