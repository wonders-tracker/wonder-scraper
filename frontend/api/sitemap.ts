export const config = {
  runtime: 'edge',
}

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://wonderstracker.com'
const API_URL = process.env.API_URL || 'https://wonder-scraper-production.up.railway.app'

interface Card {
  id: number
  slug?: string
  name: string
  set_name: string
}

interface WeekSummary {
  date: string
  week_start: string
  week_end: string
}

interface BlogPost {
  slug: string
  title: string
  description: string
  publishedAt: string
  author: string
  category: string
  tags: string[]
  image?: string
}

export default async function handler(request: Request) {
  try {
    // Fetch all cards, weekly movers, and blog manifest in parallel
    const [cardsRes, weeklyRes, blogRes] = await Promise.all([
      fetch(`${API_URL}/api/v1/cards/`, {
        headers: { 'User-Agent': 'WondersTracker-Sitemap/1.0' },
      }),
      fetch(`${API_URL}/api/v1/blog/weekly-movers?limit=52`, {
        headers: { 'User-Agent': 'WondersTracker-Sitemap/1.0' },
      }),
      fetch(`${SITE_URL}/blog-manifest.json`, {
        headers: { 'User-Agent': 'WondersTracker-Sitemap/1.0' },
      }),
    ])

    if (!cardsRes.ok) {
      throw new Error(`Cards API returned ${cardsRes.status}`)
    }
    const cards: Card[] = await cardsRes.json()

    let weeklyMovers: WeekSummary[] = []
    if (weeklyRes.ok) {
      weeklyMovers = await weeklyRes.json()
    }

    let blogPosts: BlogPost[] = []
    if (blogRes.ok) {
      blogPosts = await blogRes.json()
    }

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
      {
        loc: `${SITE_URL}/methodology`,
        changefreq: 'monthly',
        priority: '0.6',
        lastmod: today,
      },
      // Blog pages
      {
        loc: `${SITE_URL}/blog`,
        changefreq: 'daily',
        priority: '0.8',
        lastmod: today,
      },
      {
        loc: `${SITE_URL}/blog/weekly-movers`,
        changefreq: 'weekly',
        priority: '0.7',
        lastmod: today,
      },
      // Weekly movers archive
      ...weeklyMovers.map((week) => ({
        loc: `${SITE_URL}/blog/weekly-movers/${week.date}`,
        changefreq: 'monthly',
        priority: '0.6',
        lastmod: week.date,
      })),
      // Blog posts (MDX articles)
      ...blogPosts.map((post) => ({
        loc: `${SITE_URL}/blog/${post.slug}`,
        changefreq: 'monthly',
        priority: '0.7',
        lastmod: post.publishedAt.split('T')[0],
      })),
      // Dynamic card pages - use slug for SEO-friendly URLs
      ...cards.map((card) => ({
        loc: `${SITE_URL}/cards/${card.slug || card.id}`,
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
  <url>
    <loc>${SITE_URL}/blog</loc>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>${SITE_URL}/methodology</loc>
    <priority>0.6</priority>
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
