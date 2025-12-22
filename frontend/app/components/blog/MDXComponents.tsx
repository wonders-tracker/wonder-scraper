import { Link } from '@tanstack/react-router'
import { CodeBlock } from '~/components/ui/code-block'
import type { MDXComponents as MDXComponentsType } from 'mdx/types'

/**
 * Custom MDX components for blog posts
 * Uses Noto Serif for body text
 */
export const MDXComponents: MDXComponentsType = {
  // Headings - sans-serif for contrast
  h1: ({ children, id }) => (
    <h1 id={id} className="text-3xl font-bold font-sans mt-12 mb-6 scroll-mt-20">
      {children}
    </h1>
  ),
  h2: ({ children, id }) => (
    <h2 id={id} className="text-2xl font-bold font-sans mt-10 mb-4 scroll-mt-20">
      {children}
    </h2>
  ),
  h3: ({ children, id }) => (
    <h3 id={id} className="text-xl font-semibold font-sans mt-8 mb-3 scroll-mt-20">
      {children}
    </h3>
  ),
  h4: ({ children, id }) => (
    <h4 id={id} className="text-lg font-semibold font-sans mt-6 mb-2 scroll-mt-20">
      {children}
    </h4>
  ),

  // Paragraphs - serif font
  p: ({ children }) => (
    <p className="mb-6 leading-[1.8] text-foreground/90">{children}</p>
  ),

  // Links
  a: ({ href, children }) => {
    const isExternal = href?.startsWith('http')
    if (isExternal) {
      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-brand-400 hover:underline underline-offset-2"
        >
          {children}
        </a>
      )
    }
    return (
      <Link to={href || '/'} className="text-brand-400 hover:underline underline-offset-2">
        {children}
      </Link>
    )
  },

  // Lists
  ul: ({ children }) => (
    <ul className="mb-6 ml-1 space-y-3">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-6 ml-1 space-y-3 list-decimal list-inside">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="leading-[1.8] pl-2 relative before:content-['•'] before:absolute before:left-[-1rem] before:text-brand-400">
      {children}
    </li>
  ),

  // Code blocks
  pre: ({ children }) => <>{children}</>,
  code: ({ className, children }) => {
    const match = /language-(\w+)/.exec(className || '')
    if (match) {
      const language = match[1] as 'bash' | 'json' | 'typescript' | 'javascript'
      return (
        <CodeBlock
          code={String(children).replace(/\n$/, '')}
          language={language}
          className="mb-6 font-mono"
        />
      )
    }
    return (
      <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono">
        {children}
      </code>
    )
  },

  // Blockquotes
  blockquote: ({ children }) => (
    <blockquote className="border-l-4 border-brand-400 pl-6 my-8 italic text-foreground/80">
      {children}
    </blockquote>
  ),

  // Images
  img: ({ src, alt }) => (
    <figure className="my-8">
      <img
        src={src}
        alt={alt}
        className="rounded-xl w-full"
        loading="lazy"
      />
      {alt && (
        <figcaption className="text-center text-sm text-muted-foreground mt-3 font-sans">
          {alt}
        </figcaption>
      )}
    </figure>
  ),

  // Tables
  table: ({ children }) => (
    <div className="overflow-x-auto mb-6 font-sans">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-muted/50">{children}</thead>
  ),
  th: ({ children }) => (
    <th className="border border-border px-4 py-3 text-left font-semibold">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-border px-4 py-3">{children}</td>
  ),

  // Horizontal rule
  hr: () => <hr className="my-10 border-border" />,

  // Strong and emphasis
  strong: ({ children }) => (
    <strong className="font-semibold">{children}</strong>
  ),
  em: ({ children }) => <em className="italic">{children}</em>,
}

export default MDXComponents
