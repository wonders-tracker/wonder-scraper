import { createFileRoute, Link, notFound } from '@tanstack/react-router'
import { MDXProvider } from '@mdx-js/react'
import { ArrowLeft, Clock, Calendar, Twitter, Linkedin, Link as LinkIcon } from 'lucide-react'
import { getPostBySlug, getAuthor, formatDate, getAllPosts } from '~/utils/blog'
import { MDXComponents } from '~/components/blog/MDXComponents'
import { useState, useEffect } from 'react'

export const Route = createFileRoute('/blog/$slug')({
  loader: ({ params }) => {
    const post = getPostBySlug(params.slug)
    if (!post) {
      throw notFound()
    }
    return { post }
  },
  component: BlogPostPage,
  notFoundComponent: () => (
    <div className="text-center py-20">
      <h1 className="text-2xl font-bold mb-4">Post Not Found</h1>
      <p className="text-muted-foreground mb-6">
        The blog post you're looking for doesn't exist.
      </p>
      <Link
        to="/blog"
        className="inline-flex items-center gap-2 text-brand-400 hover:underline"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Blog
      </Link>
    </div>
  ),
})

function estimateReadTime(text: string): number {
  const wordsPerMinute = 200
  const words = text.split(/\s+/).length
  return Math.ceil(words / wordsPerMinute)
}

function BlogPostPage() {
  const { post } = Route.useLoaderData()
  const { frontmatter, Component } = post
  const author = getAuthor(frontmatter.author)
  const [copied, setCopied] = useState(false)

  const shareUrl = typeof window !== 'undefined' ? window.location.href : ''
  const shareText = `${frontmatter.title} - WondersTracker`

  const copyLink = () => {
    navigator.clipboard.writeText(shareUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <article className="max-w-4xl mx-auto">
      {/* Header */}
      <header className="text-center mb-12">
        {/* Breadcrumb */}
        <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground mb-6">
          <Link to="/blog" className="hover:text-foreground underline">
            Blog
          </Link>
          <span>/</span>
          <span className="capitalize">{frontmatter.category}</span>
        </div>

        {/* Meta */}
        <div className="flex items-center justify-center gap-4 text-sm text-muted-foreground mb-6">
          <span className="flex items-center gap-1">
            <Clock className="w-4 h-4" />
            5 min read
          </span>
          <span>|</span>
          <time dateTime={frontmatter.publishedAt}>
            {formatDate(frontmatter.publishedAt)}
          </time>
        </div>

        {/* Title */}
        <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold font-serif mb-6 leading-tight">
          {frontmatter.title}
        </h1>

        {/* Description */}
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-8">
          {frontmatter.description}
        </p>

        {/* Share buttons */}
        <div className="flex items-center justify-center gap-3">
          <a
            href={`https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(shareUrl)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="p-3 bg-foreground text-background rounded-lg hover:opacity-80 transition-opacity"
            aria-label="Share on Twitter"
          >
            <Twitter className="w-5 h-5" />
          </a>
          <a
            href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="p-3 bg-foreground text-background rounded-lg hover:opacity-80 transition-opacity"
            aria-label="Share on LinkedIn"
          >
            <Linkedin className="w-5 h-5" />
          </a>
          <button
            onClick={copyLink}
            className="p-3 bg-foreground text-background rounded-lg hover:opacity-80 transition-opacity relative"
            aria-label="Copy link"
          >
            <LinkIcon className="w-5 h-5" />
            {copied && (
              <span className="absolute -top-8 left-1/2 -translate-x-1/2 text-xs bg-foreground text-background px-2 py-1 rounded">
                Copied!
              </span>
            )}
          </button>
        </div>
      </header>

      {/* Author */}
      {author && (
        <div className="flex items-center gap-4 mb-10 pb-10 border-b border-border">
          <img
            src={author.avatar}
            alt={author.name}
            className="w-12 h-12 rounded-full bg-muted"
          />
          <div>
            <div className="font-semibold">{author.name}</div>
            <div className="text-sm text-muted-foreground">{author.role}</div>
          </div>
        </div>
      )}

      {/* Article body */}
      <div className="font-serif text-lg leading-relaxed">
        <MDXProvider components={MDXComponents}>
          <Component />
        </MDXProvider>
      </div>

      {/* Tags */}
      {frontmatter.tags.length > 0 && (
        <div className="mt-8 flex flex-wrap gap-2">
          {frontmatter.tags.map((tag) => (
            <span
              key={tag}
              className="bg-muted px-3 py-1 rounded-full text-sm"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Back link */}
      <div className="mt-12 pt-8 border-t border-border">
        <Link
          to="/blog"
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Blog
        </Link>
      </div>
    </article>
  )
}
