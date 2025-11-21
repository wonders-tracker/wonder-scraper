import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/cards/$cardId')({
  head: ({ params, loaderData }: any) => {
    const card = loaderData?.card
    const cardName = card?.name || 'Card Details'
    const price = card?.latest_price ? `$${card.latest_price.toFixed(2)}` : 'N/A'
    const description = `${cardName} - Current Price: ${price}. View sales history, price trends, and market data for Wonders of the First TCG.`
    
    return {
      meta: [
        {
          title: `${cardName} - WondersTracker`,
        },
        {
          name: 'description',
          content: description,
        },
        // Open Graph
        {
          property: 'og:title',
          content: `${cardName} - WondersTracker`,
        },
        {
          property: 'og:description',
          content: description,
        },
        {
          property: 'og:image',
          content: `https://wonderstracker.com/api/og?card=${encodeURIComponent(cardName)}&price=${price}`,
        },
        {
          property: 'og:url',
          content: `https://wonderstracker.com/cards/${params.cardId}`,
        },
        // Twitter
        {
          property: 'twitter:card',
          content: 'summary_large_image',
        },
        {
          property: 'twitter:title',
          content: `${cardName} - WondersTracker`,
        },
        {
          property: 'twitter:description',
          content: description,
        },
        {
          property: 'twitter:image',
          content: `https://wonderstracker.com/api/og?card=${encodeURIComponent(cardName)}&price=${price}`,
        },
      ],
    }
  },
})

