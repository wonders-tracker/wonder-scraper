import { createFileRoute } from '@tanstack/react-router'
import { siteConfig } from '~/config/site'
import { getPostBySlug, getAuthor } from '~/utils/blog'

const { name: SITE_NAME, url: SITE_URL } = siteConfig

export const Route = createFileRoute('/blog/$slug/head')({
  head: ({ params }) => {
    const post = getPostBySlug(params.slug)

    // Fallback for not found
    if (!post) {
      return {
        meta: [
          { title: `Post Not Found | ${SITE_NAME}` },
          { name: 'robots', content: 'noindex' },
        ],
      }
    }

    const { frontmatter } = post
    const author = getAuthor(frontmatter.author)
    const canonicalUrl = `${SITE_URL}/blog/${params.slug}`
    const pageTitle = `${frontmatter.title} | ${SITE_NAME}`
    const imageUrl = frontmatter.image
      ? `${SITE_URL}${frontmatter.image}`
      : `${SITE_URL}/og-image.png`

    // Article JSON-LD schema
    const articleJsonLd = {
      '@context': 'https://schema.org',
      '@type': 'Article',
      headline: frontmatter.title,
      description: frontmatter.description,
      datePublished: frontmatter.publishedAt,
      dateModified: frontmatter.publishedAt,
      author: author
        ? {
            '@type': 'Person',
            name: author.name,
            url: author.twitter ? `https://twitter.com/${author.twitter}` : undefined,
          }
        : {
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
      image: imageUrl,
      articleSection: frontmatter.category,
      keywords: frontmatter.tags.join(', '),
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
          name: frontmatter.title,
          item: canonicalUrl,
        },
      ],
    }

    return {
      meta: [
        { title: pageTitle },
        { name: 'description', content: frontmatter.description },
        { name: 'robots', content: 'index, follow' },
        { name: 'keywords', content: frontmatter.tags.join(', ') },
        { tagName: 'link', rel: 'canonical', href: canonicalUrl },

        // Open Graph - Article type
        { property: 'og:type', content: 'article' },
        { property: 'og:site_name', content: SITE_NAME },
        { property: 'og:title', content: frontmatter.title },
        { property: 'og:description', content: frontmatter.description },
        { property: 'og:url', content: canonicalUrl },
        { property: 'og:image', content: imageUrl },
        { property: 'article:published_time', content: frontmatter.publishedAt },
        { property: 'article:section', content: frontmatter.category },
        ...frontmatter.tags.map((tag) => ({
          property: 'article:tag',
          content: tag,
        })),
        ...(author
          ? [{ property: 'article:author', content: author.name }]
          : []),

        // Twitter
        { name: 'twitter:card', content: 'summary_large_image' },
        { name: 'twitter:site', content: '@WondersTracker' },
        { name: 'twitter:title', content: frontmatter.title },
        { name: 'twitter:description', content: frontmatter.description },
        { name: 'twitter:image', content: imageUrl },
        ...(author?.twitter
          ? [{ name: 'twitter:creator', content: `@${author.twitter}` }]
          : []),
      ],
      scripts: [
        {
          type: 'application/ld+json',
          children: JSON.stringify(articleJsonLd),
        },
        {
          type: 'application/ld+json',
          children: JSON.stringify(breadcrumbJsonLd),
        },
      ],
    }
  },
})
