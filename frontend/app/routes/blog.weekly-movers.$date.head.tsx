import { createFileRoute } from '@tanstack/react-router'
import { siteConfig } from '~/config/site'

const { name: SITE_NAME, url: SITE_URL } = siteConfig

export const Route = createFileRoute('/blog/weekly-movers/$date/head')({
  head: ({ params }) => {
    const { date } = params
    const formattedDate = new Date(date).toLocaleDateString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    })

    const pageTitle = `Weekly Market Movers - ${formattedDate} | ${SITE_NAME}`
    const description = `Wonders of the First TCG weekly price movers for the week ending ${formattedDate}. See top gainers, losers, volume leaders, and market trends.`
    const canonicalUrl = `${SITE_URL}/blog/weekly-movers/${date}`

    // NewsArticle JSON-LD schema for timely content
    const newsArticleJsonLd = {
      '@context': 'https://schema.org',
      '@type': 'NewsArticle',
      headline: `Weekly Market Movers - ${formattedDate}`,
      description: description,
      datePublished: date,
      dateModified: date,
      author: {
        '@type': 'Organization',
        name: SITE_NAME,
        url: SITE_URL,
      },
      publisher: {
        '@type': 'Organization',
        name: SITE_NAME,
        url: SITE_URL,
        logo: {
          '@type': 'ImageObject',
          url: `${SITE_URL}/logo.png`,
        },
      },
      mainEntityOfPage: {
        '@type': 'WebPage',
        '@id': canonicalUrl,
      },
    }

    // Breadcrumb JSON-LD
    const breadcrumbJsonLd = {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: 'Home',
          item: SITE_URL,
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: 'Blog',
          item: `${SITE_URL}/blog`,
        },
        {
          '@type': 'ListItem',
          position: 3,
          name: 'Weekly Movers',
          item: `${SITE_URL}/blog/weekly-movers`,
        },
        {
          '@type': 'ListItem',
          position: 4,
          name: formattedDate,
          item: canonicalUrl,
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
        { property: 'article:published_time', content: date },
        { property: 'article:section', content: 'Market Analysis' },

        // Twitter
        { name: 'twitter:card', content: 'summary_large_image' },
        { name: 'twitter:site', content: '@WondersTracker' },
        { name: 'twitter:title', content: pageTitle },
        { name: 'twitter:description', content: description },
      ],
      scripts: [
        {
          type: 'application/ld+json',
          children: JSON.stringify(newsArticleJsonLd),
        },
        {
          type: 'application/ld+json',
          children: JSON.stringify(breadcrumbJsonLd),
        },
      ],
    }
  },
})
