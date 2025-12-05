import { createFileRoute } from '@tanstack/react-router'

const SITE_NAME = 'WondersTracker'
const SITE_URL = 'https://wonderstracker.com'
const TWITTER_HANDLE = '@WondersTracker'

export const Route = createFileRoute('/cards/$cardId')({
  head: ({ params, loaderData }: any) => {
    const card = loaderData?.card
    const cardName = card?.name || 'Card Details'
    const setName = card?.set_name || 'Existence'
    const rarityName = card?.rarity_name || ''
    const price = card?.latest_price ? `$${card.latest_price.toFixed(2)}` : null
    const volume = card?.volume_30d || 0

    // Build rich, keyword-optimized description
    const priceText = price ? `Current Market Price: ${price}. ` : ''
    const volumeText = volume > 0 ? `${volume} sales in 30 days. ` : ''
    const description = `${cardName}${rarityName ? ` (${rarityName})` : ''} from ${setName} - ${priceText}${volumeText}Track live price history, eBay sales data, market trends, and active listings for Wonders of the First TCG cards.`

    // Construct title with key terms for SEO
    const pageTitle = `${cardName} Price & Market Data | ${setName} | ${SITE_NAME}`

    // OG Image with card info
    const ogImageParams = new URLSearchParams({
      card: cardName,
      ...(price && { price }),
      ...(rarityName && { rarity: rarityName }),
      set: setName,
    })
    const ogImageUrl = `${SITE_URL}/api/og?${ogImageParams.toString()}`

    // Canonical URL
    const canonicalUrl = `${SITE_URL}/cards/${params.cardId}`

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
    }
  },
})
