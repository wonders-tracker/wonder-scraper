import { createFileRoute } from '@tanstack/react-router'

const SITE_NAME = 'WondersTracker'
const SITE_URL = 'https://wonderstracker.com'

export const Route = createFileRoute('/methodology/head')({
  head: () => {
    const pageTitle = `Methodology - How We Calculate Prices | ${SITE_NAME}`
    const description = 'Learn how WondersTracker calculates card prices for Wonders of the First TCG. Our methodology includes data from eBay and Blokpax, updated every 15-30 minutes.'
    const canonicalUrl = `${SITE_URL}/methodology`

    // FAQ schema for the methodology page
    const faqJsonLd = {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: [
        {
          '@type': 'Question',
          name: 'Where does WondersTracker get its price data?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: 'WondersTracker aggregates market data from eBay completed sales and Blokpax listings. eBay data is updated every 15 minutes, and Blokpax data every 30 minutes.',
          },
        },
        {
          '@type': 'Question',
          name: 'How is the average price calculated?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: 'The average price is calculated as the mean of all completed sales within the selected time period. We focus on actual transaction prices rather than asking prices for accuracy.',
          },
        },
        {
          '@type': 'Question',
          name: 'What does the deal rating mean?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: 'Deal ratings compare a listing price to the average market price. Great Deal is 15%+ below average, Good Deal is 5-15% below, Fair Price is within 5%, and Overpriced is 5%+ above average.',
          },
        },
      ],
    }

    return {
      meta: [
        { title: pageTitle },
        { name: 'description', content: description },
        { name: 'robots', content: 'index, follow' },
        { tagName: 'link', rel: 'canonical', href: canonicalUrl },

        // Open Graph
        { property: 'og:type', content: 'article' },
        { property: 'og:site_name', content: SITE_NAME },
        { property: 'og:title', content: pageTitle },
        { property: 'og:description', content: description },
        { property: 'og:url', content: canonicalUrl },
      ],
      scripts: [
        {
          type: 'application/ld+json',
          children: JSON.stringify(faqJsonLd),
        },
      ],
    }
  },
})
