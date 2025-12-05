export const config = {
  runtime: 'edge',
}

const SITE_URL = 'https://wonderstracker.com'
const API_URL = 'https://wonders-scraper-production.up.railway.app'

interface Card {
  id: number
  name: string
  set_name: string
}

export default async function handler(request: Request) {
  try {
    // Fetch all cards from the API
    const response = await fetch(`${API_URL}/api/cards`)
    const cards: Card[] = await response.json()

    const today = new Date().toISOString().split('T')[0]

    // Build sitemap XML
    const urls = [
      // Static pages
      {
        loc: SITE_URL,
        changefreq: 'daily',
        priority: '1.0',
        lastmod: today,
      },
      {
        loc: `${SITE_URL}/market`,
        changefreq: 'hourly',
        priority: '0.9',
        lastmod: today,
      },
      // Dynamic card pages
      ...cards.map((card) => ({
        loc: `${SITE_URL}/cards/${card.id}`,
        changefreq: 'daily',
        priority: '0.8',
        lastmod: today,
      })),
    ]

    const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
  .map(
    (url) => `  <url>
    <loc>${url.loc}</loc>
    <lastmod>${url.lastmod}</lastmod>
    <changefreq>${url.changefreq}</changefreq>
    <priority>${url.priority}</priority>
  </url>`
  )
  .join('\n')}
</urlset>`

    return new Response(sitemap, {
      status: 200,
      headers: {
        'Content-Type': 'application/xml',
        'Cache-Control': 'public, max-age=3600, s-maxage=3600',
      },
    })
  } catch (error) {
    console.error('Sitemap generation error:', error)
    // Return a minimal sitemap on error
    const fallbackSitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>${SITE_URL}</loc>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>${SITE_URL}/market</loc>
    <priority>0.9</priority>
  </url>
</urlset>`

    return new Response(fallbackSitemap, {
      status: 200,
      headers: {
        'Content-Type': 'application/xml',
      },
    })
  }
}
