import { createFileRoute } from '@tanstack/react-router'

const SITE_NAME = 'WondersTracker'
const SITE_URL = 'https://wonderstracker.com'
const TWITTER_HANDLE = '@WondersTracker'

export const Route = createFileRoute('/cards/$cardId/head')({
  head: ({ params, loaderData }: any) => {
    const card = loaderData?.card
    const cardName = card?.name || 'Card Details'
    const setName = card?.set_name || 'Existence'
    const rarityName = card?.rarity_name || ''
    const price = card?.latest_price ? `$${card.latest_price.toFixed(2)}` : null
    const priceNum = card?.latest_price || 0
    const volume = card?.volume_30d || 0
    const lowestAsk = card?.lowest_ask || 0
    const inventory = card?.inventory || 0

    // Build rich, keyword-optimized description
    const priceText = price ? `Current Market Price: ${price}. ` : ''
    const volumeText = volume > 0 ? `${volume} sales in 30 days. ` : ''
    const description = `${cardName}${rarityName ? ` (${rarityName})` : ''} from ${setName} - ${priceText}${volumeText}Track live price history, eBay sales data, market trends, and active listings for Wonders of the First TCG cards.`

    // Construct title with key terms for SEO
    const pageTitle = `${cardName} Price & Market Data | ${setName} | ${SITE_NAME}`

    // OG Image with card-specific chart and data
    const ogImageUrl = `${SITE_URL}/api/og/${params.cardId}`

    // Canonical URL
    const canonicalUrl = `${SITE_URL}/cards/${params.cardId}`

    // JSON-LD Product Schema for rich snippets
    const jsonLd = {
      '@context': 'https://schema.org',
      '@type': 'Product',
      name: cardName,
      description: description,
      image: ogImageUrl,
      brand: {
        '@type': 'Brand',
        name: 'Wonders of the First',
      },
      category: 'Trading Card Games > Wonders of the First',
      ...(priceNum > 0 && {
        offers: {
          '@type': 'AggregateOffer',
          priceCurrency: 'USD',
          lowPrice: lowestAsk > 0 ? lowestAsk.toFixed(2) : priceNum.toFixed(2),
          highPrice: priceNum.toFixed(2),
          offerCount: inventory > 0 ? inventory : 1,
          availability: inventory > 0 ? 'https://schema.org/InStock' : 'https://schema.org/OutOfStock',
        },
      }),
      additionalProperty: [
        { '@type': 'PropertyValue', name: 'Set', value: setName },
        ...(rarityName ? [{ '@type': 'PropertyValue', name: 'Rarity', value: rarityName }] : []),
        ...(volume > 0 ? [{ '@type': 'PropertyValue', name: '30-Day Sales Volume', value: volume.toString() }] : []),
      ],
    }

    // Breadcrumb JSON-LD for site navigation
    const breadcrumbJsonLd = {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Home', item: SITE_URL },
        { '@type': 'ListItem', position: 2, name: 'Market', item: `${SITE_URL}/market` },
        { '@type': 'ListItem', position: 3, name: setName, item: `${SITE_URL}/market?set=${encodeURIComponent(setName)}` },
        { '@type': 'ListItem', position: 4, name: cardName, item: canonicalUrl },
      ],
    }

    return {
      meta: [
        // Primary Meta Tags
        { title: pageTitle },
        { name: 'description', content: description },
        { name: 'robots', content: 'index, follow, max-image-preview:large' },
        { name: 'keywords', content: `${cardName}, ${setName}, Wonders of the First, WOTF, TCG price, card value, eBay sales, market data, price history, trading card` },

        // Canonical URL
        { tagName: 'link', rel: 'canonical', href: canonicalUrl },

        // Open Graph / Facebook
        { property: 'og:type', content: 'product' },
        { property: 'og:site_name', content: SITE_NAME },
        { property: 'og:title', content: pageTitle },
        { property: 'og:description', content: description },
        { property: 'og:image', content: ogImageUrl },
        { property: 'og:image:width', content: '1200' },
        { property: 'og:image:height', content: '630' },
        { property: 'og:image:alt', content: `${cardName} - ${SITE_NAME} Price Tracker` },
        { property: 'og:url', content: canonicalUrl },
        { property: 'og:locale', content: 'en_US' },

        // Twitter Card
        { name: 'twitter:card', content: 'summary_large_image' },
        { name: 'twitter:site', content: TWITTER_HANDLE },
        { name: 'twitter:title', content: pageTitle },
        { name: 'twitter:description', content: description },
        { name: 'twitter:image', content: ogImageUrl },
        { name: 'twitter:image:alt', content: `${cardName} price and market data` },

        // Additional Product Meta (for rich snippets)
        ...(price ? [{ property: 'product:price:amount', content: price.replace('$', '') }] : []),
        ...(price ? [{ property: 'product:price:currency', content: 'USD' }] : []),
        { property: 'product:category', content: 'Trading Card Games' },
        { property: 'product:brand', content: 'Wonders of the First' },
      ],
      scripts: [
        // JSON-LD Product Schema
        {
          type: 'application/ld+json',
          children: JSON.stringify(jsonLd),
        },
        // JSON-LD Breadcrumb Schema
        {
          type: 'application/ld+json',
          children: JSON.stringify(breadcrumbJsonLd),
        },
      ],
    }
  },
})
