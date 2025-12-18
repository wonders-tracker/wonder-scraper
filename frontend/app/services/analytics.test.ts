import { describe, it, expect, vi, beforeEach } from 'vitest'
import { analytics } from './analytics'

// Get the mock gtag from setup
const mockGtag = vi.fn()

beforeEach(() => {
  // Reset gtag mock before each test
  mockGtag.mockClear()
  window.gtag = mockGtag
  sessionStorage.clear()
})

describe('Analytics Service', () => {
  describe('Core Tracking', () => {
    it('should call gtag with correct event name and params', () => {
      analytics.track('test_event', { foo: 'bar' })

      expect(mockGtag).toHaveBeenCalledWith('event', 'test_event', {
        foo: 'bar',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should handle missing gtag gracefully', () => {
      // @ts-ignore - testing undefined gtag
      window.gtag = undefined

      // Should not throw
      expect(() => analytics.track('test_event')).not.toThrow()
    })

    it('should track page views with config call', () => {
      analytics.trackPageView('/test-page', 'Test Page')

      expect(mockGtag).toHaveBeenCalledWith('config', 'G-28SPPTBF79', {
        page_path: '/test-page',
        page_title: 'Test Page',
      })
    })
  })

  describe('Auth Events', () => {
    it('should track email signup', () => {
      analytics.trackSignup('email')

      expect(mockGtag).toHaveBeenCalledWith('event', 'sign_up', {
        method: 'email',
        event_category: 'engagement',
        event_label: 'signup_email',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track Discord signup', () => {
      analytics.trackSignup('discord')

      expect(mockGtag).toHaveBeenCalledWith('event', 'sign_up', {
        method: 'discord',
        event_category: 'engagement',
        event_label: 'signup_discord',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track email login', () => {
      analytics.trackLogin('email')

      expect(mockGtag).toHaveBeenCalledWith('event', 'login', {
        method: 'email',
        event_category: 'engagement',
        event_label: 'login_email',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track Discord login', () => {
      analytics.trackLogin('discord')

      expect(mockGtag).toHaveBeenCalledWith('event', 'login', {
        method: 'discord',
        event_category: 'engagement',
        event_label: 'login_discord',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track login page view', () => {
      analytics.trackLoginPageView()

      expect(mockGtag).toHaveBeenCalledWith('event', 'login_page_view', {
        event_category: 'engagement',
        event_label: 'viewed_login_page',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track Discord login initiated', () => {
      analytics.trackDiscordLoginInitiated()

      expect(mockGtag).toHaveBeenCalledWith('event', 'discord_login_initiated', {
        event_category: 'engagement',
        event_label: 'started_discord_oauth',
        send_to: 'G-28SPPTBF79',
      })
    })
  })

  describe('User Events', () => {
    it('should track profile access', () => {
      analytics.trackProfileAccess()

      expect(mockGtag).toHaveBeenCalledWith('event', 'profile_access', {
        event_category: 'engagement',
        event_label: 'accessed_profile',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track portfolio access', () => {
      analytics.trackPortfolioAccess()

      expect(mockGtag).toHaveBeenCalledWith('event', 'portfolio_access', {
        event_category: 'engagement',
        event_label: 'accessed_portfolio',
        send_to: 'G-28SPPTBF79',
      })
    })
  })

  describe('Card/Listing Events', () => {
    it('should track card view', () => {
      analytics.trackCardView(123, 'Test Card')

      expect(mockGtag).toHaveBeenCalledWith('event', 'view_item', {
        event_category: 'engagement',
        event_label: 'viewed_card_listing',
        card_id: 123,
        card_name: 'Test Card',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track card view with string ID', () => {
      analytics.trackCardView('test-slug', 'Test Card')

      expect(mockGtag).toHaveBeenCalledWith('event', 'view_item', {
        event_category: 'engagement',
        event_label: 'viewed_card_listing',
        card_id: 'test-slug',
        card_name: 'Test Card',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track multiple listings viewed milestone', () => {
      analytics.trackMultipleListingsViewed(3)

      expect(mockGtag).toHaveBeenCalledWith('event', 'multiple_listings_viewed', {
        event_category: 'engagement',
        event_label: 'viewed_3_listings',
        listings_count: 3,
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track card view with session and trigger milestone at 3 views', () => {
      // View 3 different cards
      analytics.trackCardViewWithSession(1, 'Card 1')
      analytics.trackCardViewWithSession(2, 'Card 2')
      analytics.trackCardViewWithSession(3, 'Card 3')

      // Should have called view_item 3 times
      const viewItemCalls = mockGtag.mock.calls.filter(
        (call) => call[1] === 'view_item'
      )
      expect(viewItemCalls).toHaveLength(3)

      // Should have triggered multiple_listings_viewed once
      const milestoneCalls = mockGtag.mock.calls.filter(
        (call) => call[1] === 'multiple_listings_viewed'
      )
      expect(milestoneCalls).toHaveLength(1)
    })

    it('should not double-count same card in session', () => {
      // View same card twice
      analytics.trackCardViewWithSession(1, 'Card 1')
      analytics.trackCardViewWithSession(1, 'Card 1')
      analytics.trackCardViewWithSession(2, 'Card 2')

      // Session storage should only have 2 unique cards
      const stored = JSON.parse(sessionStorage.getItem('wt_viewed_cards') || '[]')
      expect(stored).toHaveLength(2)
      expect(stored).toContain('1')
      expect(stored).toContain('2')
    })

    it('should track add to portfolio', () => {
      analytics.trackAddToPortfolio(456, 'Dragon Card')

      expect(mockGtag).toHaveBeenCalledWith('event', 'add_to_portfolio', {
        event_category: 'engagement',
        event_label: 'added_to_portfolio',
        card_id: 456,
        card_name: 'Dragon Card',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track external link click', () => {
      analytics.trackExternalLinkClick('ebay', 123, 'Test Listing')

      expect(mockGtag).toHaveBeenCalledWith('event', 'external_link_click', {
        event_category: 'conversion',
        event_label: 'clicked_ebay_listing',
        platform: 'ebay',
        card_id: 123,
        listing_title: 'Test Listing',
        send_to: 'G-28SPPTBF79',
      })
    })
  })

  describe('Discovery Events', () => {
    it('should track search', () => {
      analytics.trackSearch('dragon mythic')

      expect(mockGtag).toHaveBeenCalledWith('event', 'search', {
        search_term: 'dragon mythic',
        event_category: 'engagement',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track filter applied', () => {
      analytics.trackFilterApplied('time_period', '30d')

      expect(mockGtag).toHaveBeenCalledWith('event', 'filter_applied', {
        event_category: 'engagement',
        filter_type: 'time_period',
        filter_value: '30d',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track product type filter', () => {
      analytics.trackFilterApplied('product_type', 'Box')

      expect(mockGtag).toHaveBeenCalledWith('event', 'filter_applied', {
        event_category: 'engagement',
        filter_type: 'product_type',
        filter_value: 'Box',
        send_to: 'G-28SPPTBF79',
      })
    })
  })

  describe('Market Events', () => {
    it('should track market page view', () => {
      analytics.trackMarketPageView()

      expect(mockGtag).toHaveBeenCalledWith('event', 'market_page_view', {
        event_category: 'engagement',
        event_label: 'viewed_market_analysis',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track chart time range interaction', () => {
      analytics.trackChartInteraction('time_range', '7d')

      expect(mockGtag).toHaveBeenCalledWith('event', 'chart_interaction', {
        event_category: 'engagement',
        interaction_type: 'time_range',
        value: '7d',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track chart type interaction', () => {
      analytics.trackChartInteraction('chart_type', 'scatter')

      expect(mockGtag).toHaveBeenCalledWith('event', 'chart_interaction', {
        event_category: 'engagement',
        interaction_type: 'chart_type',
        value: 'scatter',
        send_to: 'G-28SPPTBF79',
      })
    })
  })

  describe('Onboarding Events', () => {
    it('should track welcome page view', () => {
      analytics.trackWelcomePageView()

      expect(mockGtag).toHaveBeenCalledWith('event', 'welcome_page_view', {
        event_category: 'engagement',
        event_label: 'viewed_welcome_page',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track profile completed with username and discord', () => {
      analytics.trackProfileCompleted(true, true)

      expect(mockGtag).toHaveBeenCalledWith('event', 'profile_completed', {
        event_category: 'engagement',
        event_label: 'completed_profile',
        has_username: true,
        has_discord: true,
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track profile completed without optional fields', () => {
      analytics.trackProfileCompleted(false, false)

      expect(mockGtag).toHaveBeenCalledWith('event', 'profile_completed', {
        event_category: 'engagement',
        event_label: 'completed_profile',
        has_username: false,
        has_discord: false,
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track profile skipped', () => {
      analytics.trackProfileSkipped()

      expect(mockGtag).toHaveBeenCalledWith('event', 'profile_skipped', {
        event_category: 'engagement',
        event_label: 'skipped_profile_completion',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track upgrade page view', () => {
      analytics.trackUpgradePageView()

      expect(mockGtag).toHaveBeenCalledWith('event', 'upgrade_page_view', {
        event_category: 'engagement',
        event_label: 'viewed_upgrade_page',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track upgrade initiated', () => {
      analytics.trackUpgradeInitiated()

      expect(mockGtag).toHaveBeenCalledWith('event', 'upgrade_initiated', {
        event_category: 'conversion',
        event_label: 'started_checkout',
        send_to: 'G-28SPPTBF79',
      })
    })

    it('should track upgrade skipped', () => {
      analytics.trackUpgradeSkipped()

      expect(mockGtag).toHaveBeenCalledWith('event', 'upgrade_skipped', {
        event_category: 'engagement',
        event_label: 'skipped_upgrade',
        send_to: 'G-28SPPTBF79',
      })
    })
  })

  describe('Custom Events', () => {
    it('should allow custom events via analytics.custom()', () => {
      analytics.custom('promo_clicked', { campaign: 'holiday_2025', position: 'header' })

      expect(mockGtag).toHaveBeenCalledWith('event', 'promo_clicked', {
        campaign: 'holiday_2025',
        position: 'header',
        send_to: 'G-28SPPTBF79',
      })
    })
  })

  describe('Error Handling', () => {
    it('should handle gtag throwing an error gracefully', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockGtag.mockImplementation(() => {
        throw new Error('gtag error')
      })

      // Should not throw
      expect(() => analytics.trackSearch('test')).not.toThrow()
      expect(consoleSpy).toHaveBeenCalled()

      consoleSpy.mockRestore()
    })

    it('should still track to Vercel Analytics when gtag is not loaded', () => {
      // @ts-ignore
      window.gtag = undefined

      // Should not throw when gtag is undefined - Vercel Analytics handles it
      expect(() => analytics.track('test_event')).not.toThrow()
    })
  })
})
