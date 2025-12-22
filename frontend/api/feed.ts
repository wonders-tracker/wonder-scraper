export const config = {
  runtime: 'edge',
}

const SITE_NAME = process.env.VITE_SITE_NAME || 'WondersTracker'
const SITE_URL = process.env.VITE_SITE_URL || 'https://wonderstracker.com'
const API_URL = process.env.VITE_API_URL || 'https://wonder-scraper-production.up.railway.app'

function escapeXml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

interface WeekSummary {
  date: string
  week_start: string
  week_end: string
  total_sales: number
  total_volume: number
}

export default async function handler(request: Request) {
  try {
    // Fetch weekly movers for RSS feed
    const weeklyRes = await fetch(`${API_URL}/api/v1/blog/weekly-movers?limit=20`, {
      headers: {
        'User-Agent': 'WondersTracker-RSS/1.0',
        Accept: 'application/json',
      },
    })

    let weeklyItems: WeekSummary[] = []
    if (weeklyRes.ok) {
      weeklyItems = await weeklyRes.json()
    }

    const items = weeklyItems.map((week) => {
      const weekStart = new Date(week.week_start).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      })
      const weekEnd = new Date(week.week_end).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })

      return {
        title: `Weekly Market Movers: ${weekStart} - ${weekEnd}`,
        link: `${SITE_URL}/blog/weekly-movers/${week.date}`,
        description: `Wonders of the First TCG weekly market report. ${week.total_sales} sales totaling $${week.total_volume.toLocaleString()}.`,
        pubDate: new Date(week.date).toUTCString(),
        guid: `${SITE_URL}/blog/weekly-movers/${week.date}`,
      }
    })

    const rss = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(SITE_NAME)} Blog</title>
    <link>${SITE_URL}/blog</link>
    <description>Market analysis, weekly price movers, and guides for Wonders of the First TCG</description>
    <language>en-us</language>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
    <atom:link href="${SITE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
    <image>
      <url>${SITE_URL}/logo.png</url>
      <title>${escapeXml(SITE_NAME)}</title>
      <link>${SITE_URL}</link>
    </image>
    ${items
      .map(
        (item) => `
    <item>
      <title>${escapeXml(item.title)}</title>
      <link>${item.link}</link>
      <description>${escapeXml(item.description)}</description>
      <pubDate>${item.pubDate}</pubDate>
      <guid isPermaLink="true">${item.guid}</guid>
    </item>`
      )
      .join('')}
  </channel>
</rss>`

    return new Response(rss, {
      headers: {
        'Content-Type': 'application/rss+xml; charset=utf-8',
        'Cache-Control': 'public, max-age=3600, s-maxage=3600',
      },
    })
  } catch (error) {
    console.error('RSS feed error:', error)

    // Return minimal valid RSS feed on error
    const fallbackRss = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>${escapeXml(SITE_NAME)} Blog</title>
    <link>${SITE_URL}/blog</link>
    <description>Market analysis for Wonders of the First TCG</description>
  </channel>
</rss>`

    return new Response(fallbackRss, {
      headers: {
        'Content-Type': 'application/rss+xml; charset=utf-8',
        'Cache-Control': 'public, max-age=300',
      },
    })
  }
}
