import { createFileRoute } from '@tanstack/react-router'
import { siteConfig } from '~/config/site'

const { name: SITE_NAME, url: SITE_URL } = siteConfig

export const Route = createFileRoute('/blog/head')({
  head: () => {
    const pageTitle = `Blog - Market Analysis & Guides | ${SITE_NAME}`
    const description = 'Market analysis, weekly price movers, and guides for Wonders of the First TCG. Stay updated with the latest market trends and investment insights.'
    const canonicalUrl = `${SITE_URL}/blog`

    // Blog JSON-LD schema
    const blogJsonLd = {
      '@context': 'https://schema.org',
      '@type': 'Blog',
      name: `${SITE_NAME} Blog`,
      description: description,
      url: canonicalUrl,
      publisher: {
        '@type': 'Organization',
        name: SITE_NAME,
        url: SITE_URL,
        logo: {
          '@type': 'ImageObject',
          url: `${SITE_URL}/logo.png`,
        },
      },
    }

    return {
      meta: [
        { title: pageTitle },
        { name: 'description', content: description },
        { name: 'robots', content: 'index, follow' },
        { tagName: 'link', rel: 'canonical', href: canonicalUrl },

        // Open Graph
        { property: 'og:type', content: 'website' },
        { property: 'og:site_name', content: SITE_NAME },
        { property: 'og:title', content: pageTitle },
        { property: 'og:description', content: description },
        { property: 'og:url', content: canonicalUrl },

        // Twitter
        { name: 'twitter:card', content: 'summary' },
        { name: 'twitter:site', content: '@WondersTracker' },
        { name: 'twitter:title', content: pageTitle },
        { name: 'twitter:description', content: description },
      ],
      scripts: [
        {
          type: 'application/ld+json',
          children: JSON.stringify(blogJsonLd),
        },
      ],
      links: [
        { rel: 'alternate', type: 'application/rss+xml', title: `${SITE_NAME} Blog RSS`, href: `${SITE_URL}/feed.xml` },
      ],
    }
  },
})
