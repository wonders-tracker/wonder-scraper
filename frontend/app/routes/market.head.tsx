import { createFileRoute } from '@tanstack/react-router'

const SITE_NAME = 'WondersTracker'
const SITE_URL = 'https://wonderstracker.com'
const TWITTER_HANDLE = '@WondersTracker'

export const Route = createFileRoute('/market')({
  head: () => {
    const pageTitle = `Market Analysis & Trends | ${SITE_NAME}`
    const description = 'Comprehensive market analysis for Wonders of the First TCG. View real-time sales trends, trading volume, price movements, and discover undervalued cards with our deal rating system.'
    const canonicalUrl = `${SITE_URL}/market`
    const ogImageUrl = `${SITE_URL}/api/og?card=${encodeURIComponent('Market Analysis')}&set=${encodeURIComponent('WOTF Trading Data')}`

    // CollectionPage JSON-LD schema for market overview
    const collectionJsonLd = {
      '@context': 'https://schema.org',
      '@type': 'CollectionPage',
      name: 'Wonders of the First Market Analysis',
      description: description,
      url: canonicalUrl,
      isPartOf: {
        '@type': 'WebSite',
        name: SITE_NAME,
        url: SITE_URL,
      },
      breadcrumb: {
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: SITE_URL },
          { '@type': 'ListItem', position: 2, name: 'Market', item: canonicalUrl },
        ],
      },
    }

    return {
      meta: [
        { title: pageTitle },
        { name: 'description', content: description },
        { name: 'robots', content: 'index, follow, max-image-preview:large' },
        { name: 'keywords', content: 'WOTF market analysis, TCG trading volume, card price trends, market data, deal finder, undervalued cards, trading card investment' },

        // Canonical URL
        { tagName: 'link', rel: 'canonical', href: canonicalUrl },

        // Open Graph
        { property: 'og:type', content: 'website' },
        { property: 'og:site_name', content: SITE_NAME },
        { property: 'og:title', content: pageTitle },
        { property: 'og:description', content: description },
        { property: 'og:image', content: ogImageUrl },
        { property: 'og:image:width', content: '1200' },
        { property: 'og:image:height', content: '630' },
        { property: 'og:image:alt', content: 'WOTF Market Analysis Dashboard' },
        { property: 'og:url', content: canonicalUrl },
        { property: 'og:locale', content: 'en_US' },

        // Twitter Card
        { name: 'twitter:card', content: 'summary_large_image' },
        { name: 'twitter:site', content: TWITTER_HANDLE },
        { name: 'twitter:title', content: pageTitle },
        { name: 'twitter:description', content: description },
        { name: 'twitter:image', content: ogImageUrl },
        { name: 'twitter:image:alt', content: 'WOTF TCG market trends and analysis' },
      ],
      scripts: [
        {
          type: 'application/ld+json',
          children: JSON.stringify(collectionJsonLd),
        },
      ],
    }
  },
})
