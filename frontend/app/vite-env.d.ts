/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// MDX module declarations
declare module '*.mdx' {
  import type { ComponentType } from 'react'

  export const frontmatter: {
    title: string
    slug: string
    description: string
    publishedAt: string
    author: string
    category: 'analysis' | 'news' | 'guide'
    tags: string[]
    image?: string
  }

  const Component: ComponentType
  export default Component
}

