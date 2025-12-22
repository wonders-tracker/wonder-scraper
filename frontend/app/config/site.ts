/**
 * Site configuration - uses environment variables with fallbacks
 */

export const siteConfig = {
  name: import.meta.env.VITE_SITE_NAME || 'WondersTracker',
  url: import.meta.env.VITE_SITE_URL || 'https://wonderstracker.com',
  twitter: import.meta.env.VITE_TWITTER_HANDLE || '@WondersTracker',
  description: 'Real-time price tracking for Wonders of the First TCG',
  apiUrl: import.meta.env.VITE_API_URL || 'https://wonder-scraper-production.up.railway.app',
} as const

export type SiteConfig = typeof siteConfig
