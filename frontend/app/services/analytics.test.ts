import { describe, it, expect, vi, beforeEach } from 'vitest'
import { analytics } from './analytics'

// Mock @vercel/analytics
vi.mock('@vercel/analytics', () => ({
  track: vi.fn(),
}))

// Get the mocked track function
import { track as vercelTrack } from '@vercel/analytics'
const mockedTrack = vi.mocked(vercelTrack)

beforeEach(() => {
  mockedTrack.mockClear()
  sessionStorage.clear()
})

describe('Analytics Service', () => {
  describe('Core Tracking', () => {
    it('should call vercel track with correct event name and params', () => {
      analytics.track('test_event', { foo: 'bar' })

      expect(mockedTrack).toHaveBeenCalledWith('test_event', { foo: 'bar' })
    })

    it('should handle errors gracefully', () => {
      const consoleSpy = vi.spyOn(console, 'debug').mockImplementation(() => {})
      mockedTrack.mockImplementation(() => {
        throw new Error('track error')
      })

      // Should not throw
      expect(() => analytics.track('test_event')).not.toThrow()

      consoleSpy.mockRestore()
    })

    it('should truncate long event names to 255 chars', () => {
      const longName = 'a'.repeat(300)
      analytics.track(longName)

      expect(mockedTrack).toHaveBeenCalledWith('a'.repeat(255), undefined)
    })

    it('should truncate long string values to 255 chars', () => {
      const longValue = 'b'.repeat(300)
      analytics.track('test_event', { data: longValue })

      expect(mockedTrack).toHaveBeenCalledWith('test_event', {
        data: 'b'.repeat(255),
      })
    })

    it('should remove undefined values from params', () => {
      analytics.track('test_event', { defined: 'yes', notDefined: undefined })

      expect(mockedTrack).toHaveBeenCalledWith('test_event', {
        defined: 'yes',
      })
    })
  })

  describe('Auth Events', () => {
    it('should track email signup', () => {
      analytics.trackSignup('email')

      expect(mockedTrack).toHaveBeenCalledWith('sign_up', { method: 'email' })
    })

    it('should track Discord signup', () => {
      analytics.trackSignup('discord')

      expect(mockedTrack).toHaveBeenCalledWith('sign_up', {
        method: 'discord',
      })
    })

    it('should track email login', () => {
      analytics.trackLogin('email')

      expect(mockedTrack).toHaveBeenCalledWith('login', { method: 'email' })
    })

    it('should track Discord login', () => {
      analytics.trackLogin('discord')

      expect(mockedTrack).toHaveBeenCalledWith('login', {
        method: 'discord',
      })
    })

    it('should track login page view', () => {
      analytics.trackLoginPageView()

      expect(mockedTrack).toHaveBeenCalledWith('login_page_view', undefined)
    })

    it('should track Discord login initiated', () => {
      analytics.trackDiscordLoginInitiated()

      expect(mockedTrack).toHaveBeenCalledWith(
        'discord_login_initiated',
        undefined
      )
    })
  })

  describe('User Events', () => {
    it('should track profile access', () => {
      analytics.trackProfileAccess()

      expect(mockedTrack).toHaveBeenCalledWith('profile_access', undefined)
    })

    it('should track portfolio access', () => {
      analytics.trackPortfolioAccess()

      expect(mockedTrack).toHaveBeenCalledWith('portfolio_access', undefined)
    })
  })

  describe('Card/Listing Events', () => {
    it('should track card view', () => {
      analytics.trackCardView(123, 'Test Card')

      expect(mockedTrack).toHaveBeenCalledWith('view_item', {
        card_id: '123',
        card_name: 'Test Card',
      })
    })

    it('should track card view with string ID', () => {
      analytics.trackCardView('test-slug', 'Test Card')

      expect(mockedTrack).toHaveBeenCalledWith('view_item', {
        card_id: 'test-slug',
        card_name: 'Test Card',
      })
    })

    it('should track multiple listings viewed milestone', () => {
      analytics.trackMultipleListingsViewed(3)

      expect(mockedTrack).toHaveBeenCalledWith('multiple_listings_viewed', {
        listings_count: 3,
      })
    })

    it('should track card view with session and trigger milestone at 3 views', () => {
      // View 3 different cards
      analytics.trackCardViewWithSession(1, 'Card 1')
      analytics.trackCardViewWithSession(2, 'Card 2')
      analytics.trackCardViewWithSession(3, 'Card 3')

      // Should have called view_item 3 times
      const viewItemCalls = mockedTrack.mock.calls.filter(
        (call) => call[0] === 'view_item'
      )
      expect(viewItemCalls).toHaveLength(3)

      // Should have triggered multiple_listings_viewed once
      const milestoneCalls = mockedTrack.mock.calls.filter(
        (call) => call[0] === 'multiple_listings_viewed'
      )
      expect(milestoneCalls).toHaveLength(1)
    })

    it('should not double-count same card in session', () => {
      // View same card twice
      analytics.trackCardViewWithSession(1, 'Card 1')
      analytics.trackCardViewWithSession(1, 'Card 1')
      analytics.trackCardViewWithSession(2, 'Card 2')

      // Session storage should only have 2 unique cards
      const stored = JSON.parse(
        sessionStorage.getItem('wt_viewed_cards') || '[]'
      )
      expect(stored).toHaveLength(2)
      expect(stored).toContain('1')
      expect(stored).toContain('2')
    })

    it('should track add to portfolio', () => {
      analytics.trackAddToPortfolio(456, 'Dragon Card')

      expect(mockedTrack).toHaveBeenCalledWith('add_to_portfolio', {
        card_id: '456',
        card_name: 'Dragon Card',
      })
    })

    it('should track external link click', () => {
      analytics.trackExternalLinkClick('ebay', 123, 'Test Listing')

      expect(mockedTrack).toHaveBeenCalledWith('external_link_click', {
        platform: 'ebay',
        card_id: '123',
        listing_title: 'Test Listing',
      })
    })
  })

  describe('Discovery Events', () => {
    it('should track search', () => {
      analytics.trackSearch('dragon mythic')

      expect(mockedTrack).toHaveBeenCalledWith('search', {
        search_term: 'dragon mythic',
      })
    })

    describe('Filter Applied', () => {
      it('should track time_period filter', () => {
        analytics.trackFilterApplied('time_period', '30d')

        expect(mockedTrack).toHaveBeenCalledWith('filter_applied', {
          filter_type: 'time_period',
          filter_value: '30d',
        })
      })

      it('should track product_type filter', () => {
        analytics.trackFilterApplied('product_type', 'Box')

        expect(mockedTrack).toHaveBeenCalledWith('filter_applied', {
          filter_type: 'product_type',
          filter_value: 'Box',
        })
      })

      it('should track set filter', () => {
        analytics.trackFilterApplied('set', 'Star Wars: Destiny')

        expect(mockedTrack).toHaveBeenCalledWith('filter_applied', {
          filter_type: 'set',
          filter_value: 'Star Wars: Destiny',
        })
      })

      it('should track condition filter', () => {
        analytics.trackFilterApplied('condition', 'Near Mint')

        expect(mockedTrack).toHaveBeenCalledWith('filter_applied', {
          filter_type: 'condition',
          filter_value: 'Near Mint',
        })
      })

      it('should track printing filter', () => {
        analytics.trackFilterApplied('printing', 'First Edition')

        expect(mockedTrack).toHaveBeenCalledWith('filter_applied', {
          filter_type: 'printing',
          filter_value: 'First Edition',
        })
      })

      it('should track card_type filter', () => {
        analytics.trackFilterApplied('card_type', 'Character')

        expect(mockedTrack).toHaveBeenCalledWith('filter_applied', {
          filter_type: 'card_type',
          filter_value: 'Character',
        })
      })

      it('should track color filter', () => {
        analytics.trackFilterApplied('color', 'Blue')

        expect(mockedTrack).toHaveBeenCalledWith('filter_applied', {
          filter_type: 'color',
          filter_value: 'Blue',
        })
      })

      it('should track rarity filter', () => {
        analytics.trackFilterApplied('rarity', 'Legendary')

        expect(mockedTrack).toHaveBeenCalledWith('filter_applied', {
          filter_type: 'rarity',
          filter_value: 'Legendary',
        })
      })
    })

    describe('Filter Removed', () => {
      it('should track single filter removal', () => {
        analytics.trackFilterRemoved('set', 'Star Wars: Destiny')

        expect(mockedTrack).toHaveBeenCalledWith('filter_removed', {
          filter_type: 'set',
          filter_value: 'Star Wars: Destiny',
        })
      })

      it('should track rarity filter removal', () => {
        analytics.trackFilterRemoved('rarity', 'Mythic')

        expect(mockedTrack).toHaveBeenCalledWith('filter_removed', {
          filter_type: 'rarity',
          filter_value: 'Mythic',
        })
      })
    })

    describe('Filters Cleared', () => {
      it('should track clearing all filters with count', () => {
        analytics.trackFiltersCleared(3)

        expect(mockedTrack).toHaveBeenCalledWith('filters_cleared', {
          filter_count: 3,
        })
      })

      it('should track clearing single filter', () => {
        analytics.trackFiltersCleared(1)

        expect(mockedTrack).toHaveBeenCalledWith('filters_cleared', {
          filter_count: 1,
        })
      })
    })
  })

  describe('Market Events', () => {
    it('should track market page view', () => {
      analytics.trackMarketPageView()

      expect(mockedTrack).toHaveBeenCalledWith('market_page_view', undefined)
    })

    it('should track chart time range interaction', () => {
      analytics.trackChartInteraction('time_range', '7d')

      expect(mockedTrack).toHaveBeenCalledWith('chart_interaction', {
        interaction_type: 'time_range',
        value: '7d',
      })
    })

    it('should track chart type interaction', () => {
      analytics.trackChartInteraction('chart_type', 'scatter')

      expect(mockedTrack).toHaveBeenCalledWith('chart_interaction', {
        interaction_type: 'chart_type',
        value: 'scatter',
      })
    })
  })

  describe('Onboarding Events', () => {
    it('should track welcome page view', () => {
      analytics.trackWelcomePageView()

      expect(mockedTrack).toHaveBeenCalledWith('welcome_page_view', undefined)
    })

    it('should track profile completed with username and discord', () => {
      analytics.trackProfileCompleted(true, true)

      expect(mockedTrack).toHaveBeenCalledWith('profile_completed', {
        has_username: true,
        has_discord: true,
      })
    })

    it('should track profile completed without optional fields', () => {
      analytics.trackProfileCompleted(false, false)

      expect(mockedTrack).toHaveBeenCalledWith('profile_completed', {
        has_username: false,
        has_discord: false,
      })
    })

    it('should track profile skipped', () => {
      analytics.trackProfileSkipped()

      expect(mockedTrack).toHaveBeenCalledWith('profile_skipped', undefined)
    })

    it('should track upgrade page view', () => {
      analytics.trackUpgradePageView()

      expect(mockedTrack).toHaveBeenCalledWith('upgrade_page_view', undefined)
    })

    it('should track upgrade initiated', () => {
      analytics.trackUpgradeInitiated()

      expect(mockedTrack).toHaveBeenCalledWith('upgrade_initiated', undefined)
    })

    it('should track upgrade skipped', () => {
      analytics.trackUpgradeSkipped()

      expect(mockedTrack).toHaveBeenCalledWith('upgrade_skipped', undefined)
    })
  })

  describe('Custom Events', () => {
    it('should allow custom events via analytics.custom()', () => {
      analytics.custom('promo_clicked', {
        campaign: 'holiday_2025',
        position: 'header',
      })

      expect(mockedTrack).toHaveBeenCalledWith('promo_clicked', {
        campaign: 'holiday_2025',
        position: 'header',
      })
    })
  })
})
