export const config = {
  matcher: '/cards/:path*',
}

// List of known social media/bot user agents
const CRAWLER_USER_AGENTS = [
  'facebookexternalhit',
  'Facebot',
  'Twitterbot',
  'LinkedInBot',
  'WhatsApp',
  'Slackbot',
  'TelegramBot',
  'Discordbot',
  'Pinterest',
  'Googlebot',
  'bingbot',
]

function isCrawler(userAgent: string | null): boolean {
  if (!userAgent) return false
  return CRAWLER_USER_AGENTS.some(bot =>
    userAgent.toLowerCase().includes(bot.toLowerCase())
  )
}

export default function middleware(request: Request): Response | undefined {
  const userAgent = request.headers.get('user-agent')
  const url = new URL(request.url)
  const pathname = url.pathname

  // Only intercept /cards/:cardId routes for crawlers
  const cardMatch = pathname.match(/^\/cards\/(\d+)$/)

  if (cardMatch && isCrawler(userAgent)) {
    const cardId = cardMatch[1]
    const siteUrl = 'https://wonderstracker.com'
    const ogImageUrl = `${siteUrl}/api/og/${cardId}`

    // Return minimal HTML with OG tags for crawlers
    const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta property="og:type" content="product" />
  <meta property="og:site_name" content="WondersTracker" />
  <meta property="og:title" content="Card Price & Market Data | WondersTracker" />
  <meta property="og:description" content="Track real-time market prices, sales history, and inventory for Wonders of the First TCG cards." />
  <meta property="og:image" content="${ogImageUrl}" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:url" content="${siteUrl}/cards/${cardId}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:image" content="${ogImageUrl}" />
  <title>WondersTracker - Card Details</title>
</head>
<body></body>
</html>`

    return new Response(html, {
      status: 200,
      headers: {
        'Content-Type': 'text/html',
        'Cache-Control': 'public, max-age=3600',
      },
    })
  }

  // Return undefined to continue to the next middleware/static file
  return undefined
}
