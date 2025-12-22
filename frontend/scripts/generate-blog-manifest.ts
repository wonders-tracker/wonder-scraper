#!/usr/bin/env npx tsx
/**
 * Generate blog manifest from MDX frontmatter
 * Run: npx tsx scripts/generate-blog-manifest.ts
 * Or: npm run generate:blog-manifest
 */

import { readdir, readFile, writeFile } from 'fs/promises'
import { join } from 'path'
import matter from 'gray-matter'

const POSTS_DIR = join(process.cwd(), 'app/content/blog/posts')
const OUTPUT_FILE = join(process.cwd(), 'public/blog-manifest.json')

interface BlogPostMeta {
  slug: string
  title: string
  description: string
  publishedAt: string
  author: string
  category: string
  tags: string[]
  image?: string
}

async function generateManifest() {
  console.log('Generating blog manifest...')

  const files = await readdir(POSTS_DIR)
  const mdxFiles = files.filter((f) => f.endsWith('.mdx'))

  const posts: BlogPostMeta[] = []

  for (const file of mdxFiles) {
    const content = await readFile(join(POSTS_DIR, file), 'utf-8')
    const { data } = matter(content)

    // Extract slug from frontmatter or filename
    const filenameSlug = file.replace('.mdx', '').replace(/^\d{4}-\d{2}-\d{2}-/, '')
    const slug = data.slug || filenameSlug

    posts.push({
      slug,
      title: data.title,
      description: data.description,
      publishedAt: data.publishedAt,
      author: data.author,
      category: data.category,
      tags: data.tags || [],
      image: data.image,
    })
  }

  // Sort by date, newest first
  posts.sort((a, b) => new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime())

  await writeFile(OUTPUT_FILE, JSON.stringify(posts, null, 2))
  console.log(`Generated ${OUTPUT_FILE} with ${posts.length} posts`)
}

generateManifest().catch(console.error)
