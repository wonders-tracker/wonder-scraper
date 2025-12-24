import authors from '~/content/blog/authors.json'

export interface BlogPostFrontmatter {
  title: string
  slug: string
  description: string
  publishedAt: string
  author: string
  category: 'analysis' | 'news' | 'guide'
  tags: string[]
  image?: string
  readTime?: number
}

export interface BlogPost {
  frontmatter: BlogPostFrontmatter
  slug: string
  Component: React.ComponentType
}

export interface Author {
  name: string
  role: string
  avatar: string
  twitter?: string
  bio: string
}

// Glob import all MDX files at build time
// This is resolved at compile time by Vite
const mdxModules = import.meta.glob<{
  default: React.ComponentType
  frontmatter: BlogPostFrontmatter
}>('../content/blog/posts/*.mdx', { eager: true })

/**
 * Get all blog posts sorted by date (newest first)
 */
export function getAllPosts(): BlogPost[] {
  const posts = Object.entries(mdxModules).map(([filepath, module]) => {
    // Extract slug from filepath: ../content/blog/posts/2024-12-20-my-post.mdx -> my-post
    const filename = filepath.split('/').pop()?.replace('.mdx', '') || ''
    // Remove date prefix if present (e.g., 2024-12-20-my-post -> my-post)
    const slug = module.frontmatter?.slug || filename.replace(/^\d{4}-\d{2}-\d{2}-/, '')

    return {
      frontmatter: module.frontmatter,
      slug,
      Component: module.default,
    }
  })

  // Sort by publishedAt date, newest first
  return posts.sort((a, b) => {
    const dateA = new Date(a.frontmatter.publishedAt).getTime()
    const dateB = new Date(b.frontmatter.publishedAt).getTime()
    return dateB - dateA
  })
}

/**
 * Get a single post by slug
 */
export function getPostBySlug(slug: string): BlogPost | undefined {
  const posts = getAllPosts()
  return posts.find((post) => post.slug === slug)
}

/**
 * Get posts by category
 */
export function getPostsByCategory(category: string): BlogPost[] {
  return getAllPosts().filter((post) => post.frontmatter.category === category)
}

/**
 * Get posts by tag
 */
export function getPostsByTag(tag: string): BlogPost[] {
  return getAllPosts().filter((post) => post.frontmatter.tags.includes(tag))
}

/**
 * Get author info by id
 */
export function getAuthor(authorId: string): Author | undefined {
  return (authors as Record<string, Author>)[authorId]
}

/**
 * Format date for display
 */
export function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

/**
 * Get all unique tags from all posts
 */
export function getAllTags(): string[] {
  const tags = new Set<string>()
  getAllPosts().forEach((post) => {
    post.frontmatter.tags.forEach((tag) => tags.add(tag))
  })
  return Array.from(tags).sort()
}
