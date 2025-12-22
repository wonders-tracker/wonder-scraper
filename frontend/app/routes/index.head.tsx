import { createFileRoute } from '@tanstack/react-router'
import { siteConfig } from '~/config/site'

const { name: SITE_NAME, url: SITE_URL, twitter: TWITTER_HANDLE } = siteConfig

export const Route = createFileRoute('/index/head')({
  head: () => {
    const pageTitle = `${SITE_NAME} - Real-Time Wonders of the First TCG Price Tracker`
    const description = 'Track live card prices, market trends, and eBay sales data for Wonders of the First TCG. Browse 500+ cards with real-time pricing, sales volume, and deal ratings. Find the best prices on singles, boxes, and sealed products.'
    const ogImageUrl = `${SITE_URL}/api/og?card=${encodeURIComponent(SITE_NAME)}&set=${encodeURIComponent('Live TCG Price Tracker')}`

    // Website JSON-LD schema
    const websiteJsonLd = {
      '@context': 'https://schema.org',
      '@type': 'WebSite',
      name: SITE_NAME,
      url: SITE_URL,
      description: description,
      potentialAction: {
        '@type': 'SearchAction',
        target: {
          '@type': 'EntryPoint',
          urlTemplate: `${SITE_URL}/?search={search_term_string}`,
        },
        'query-input': 'required name=search_term_string',
      },
    }

    // Organization JSON-LD schema
    const organizationJsonLd = {
      '@context': 'https://schema.org',
      '@type': 'Organization',
      name: SITE_NAME,
      url: SITE_URL,
      logo: `${SITE_URL}/logo.png`,
      sameAs: [
        'https://twitter.com/WondersTracker',
      ],
    }

    // FAQ JSON-LD schema for rich snippets
    const faqJsonLd = {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: [
        {
          '@type': 'Question',
          name: 'What is WondersTracker?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: 'WondersTracker is a real-time price tracking platform for Wonders of the First TCG. We aggregate sales data from eBay and Blokpax to provide accurate market values, price trends, and deal ratings for every card in the game.',
          },
        },
        {
          '@type': 'Question',
          name: 'How often are prices updated?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: 'Prices are updated continuously throughout the day. eBay sales data is refreshed every 15 minutes, and Blokpax listings are updated every 30 minutes to ensure you always have the most current market information.',
          },
        },
        {
          '@type': 'Question',
          name: 'Where does the price data come from?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: 'Our price data is sourced from actual completed sales on eBay and active listings on Blokpax. We track sold prices, not just asking prices, to give you accurate market values based on real transactions.',
          },
        },
        {
          '@type': 'Question',
          name: 'Is WondersTracker free to use?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: 'Yes, WondersTracker is free to use. You can browse all card prices, view market trends, and track price history without creating an account. Premium features like portfolio tracking are available for registered users.',
          },
        },
      ],
    }

    return {
      meta: [
        { title: pageTitle },
        { name: 'description', content: description },
        { name: 'robots', content: 'index, follow, max-image-preview:large' },
        { name: 'keywords', content: 'Wonders of the First, WOTF, TCG prices, trading card game, card value, eBay sales, market tracker, price history, card singles, sealed product' },

        // Canonical URL
        { tagName: 'link', rel: 'canonical', href: SITE_URL },

        // Open Graph
        { property: 'og:type', content: 'website' },
        { property: 'og:site_name', content: SITE_NAME },
        { property: 'og:title', content: pageTitle },
        { property: 'og:description', content: description },
        { property: 'og:image', content: ogImageUrl },
        { property: 'og:image:width', content: '1200' },
        { property: 'og:image:height', content: '630' },
        { property: 'og:image:alt', content: `${SITE_NAME} - TCG Price Tracker` },
        { property: 'og:url', content: SITE_URL },
        { property: 'og:locale', content: 'en_US' },

        // Twitter Card
        { name: 'twitter:card', content: 'summary_large_image' },
        { name: 'twitter:site', content: TWITTER_HANDLE },
        { name: 'twitter:title', content: pageTitle },
        { name: 'twitter:description', content: description },
        { name: 'twitter:image', content: ogImageUrl },
        { name: 'twitter:image:alt', content: `${SITE_NAME} - Real-time TCG market data` },
      ],
      scripts: [
        {
          type: 'application/ld+json',
          children: JSON.stringify(websiteJsonLd),
        },
        {
          type: 'application/ld+json',
          children: JSON.stringify(organizationJsonLd),
        },
        {
          type: 'application/ld+json',
          children: JSON.stringify(faqJsonLd),
        },
      ],
    }
  },
})
