import { createFileRoute, Link } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Calendar, BookOpen, TrendingUp } from 'lucide-react'

export const Route = createFileRoute('/blog/')({
  component: BlogIndexPage,
})

interface BlogPost {
  slug: string
  title: string
  description: string
  publishedAt: string
  author: string
  category: string
  tags: string[]
}

function BlogIndexPage() {
  const { data: posts, isLoading } = useQuery<BlogPost[]>({
    queryKey: ['blog-posts'],
    queryFn: async () => {
      const res = await fetch('/blog-manifest.json')
      if (!res.ok) return []
      return res.json()
    },
    staleTime: 60 * 60 * 1000,
  })

  const featuredPost = posts?.[0]
  const recentPosts = posts?.slice(1, 7) || []

  return (
    <div className="max-w-4xl mx-auto space-y-12">
      {/* Header */}
      <div>
        <h1 className="text-4xl md:text-5xl font-bold font-serif mb-4">Blog</h1>
        <p className="text-lg text-muted-foreground">
          Market analysis, strategy guides, and news for Wonders of the First TCG
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-8 animate-pulse">
          <div className="h-64 bg-muted rounded-xl" />
          <div className="grid md:grid-cols-2 gap-6">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-40 bg-muted rounded-xl" />
            ))}
          </div>
        </div>
      ) : posts && posts.length > 0 ? (
        <>
          {/* Featured Post */}
          {featuredPost && (
            <Link
              to="/blog/$slug"
              params={{ slug: featuredPost.slug }}
              className="block group"
            >
              <article className="relative p-8 bg-gradient-to-br from-brand-400/10 to-brand-400/5 border border-brand-400/20 rounded-2xl hover:border-brand-400/40 transition-colors">
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-4">
                  <span className="px-2 py-0.5 bg-brand-400/20 text-brand-400 rounded-full text-xs font-medium uppercase tracking-wide">
                    Featured
                  </span>
                  <span>·</span>
                  <span className="capitalize">{featuredPost.category}</span>
                  <span>·</span>
                  <time dateTime={featuredPost.publishedAt}>
                    {new Date(featuredPost.publishedAt).toLocaleDateString('en-US', {
                      month: 'long',
                      day: 'numeric',
                      year: 'numeric',
                    })}
                  </time>
                </div>
                <h2 className="text-2xl md:text-3xl font-bold font-serif mb-3 group-hover:text-brand-400 transition-colors">
                  {featuredPost.title}
                </h2>
                <p className="text-muted-foreground text-lg leading-relaxed mb-4">
                  {featuredPost.description}
                </p>
                <span className="inline-flex items-center gap-2 text-brand-400 font-medium">
                  Read more <ArrowRight className="w-4 h-4" />
                </span>
              </article>
            </Link>
          )}

          {/* Recent Posts Grid */}
          {recentPosts.length > 0 && (
            <div>
              <h2 className="text-xl font-bold mb-6">Recent Posts</h2>
              <div className="grid md:grid-cols-2 gap-6">
                {recentPosts.map((post) => (
                  <Link
                    key={post.slug}
                    to="/blog/$slug"
                    params={{ slug: post.slug }}
                    className="group block p-6 bg-card border border-border rounded-xl hover:border-brand-400/50 transition-colors"
                  >
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mb-3">
                      <span className="px-2 py-0.5 bg-muted rounded-full capitalize">{post.category}</span>
                      <span>·</span>
                      <time dateTime={post.publishedAt}>
                        {new Date(post.publishedAt).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                        })}
                      </time>
                    </div>
                    <h3 className="font-semibold text-lg mb-2 group-hover:text-brand-400 transition-colors">
                      {post.title}
                    </h3>
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {post.description}
                    </p>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Categories */}
          <div className="border-t border-border pt-8">
            <h2 className="text-xl font-bold mb-6">Browse by Category</h2>
            <div className="flex flex-wrap gap-3">
              <Link
                to="/blog"
                search={{ category: 'analysis' }}
                className="px-4 py-2 bg-card border border-border rounded-lg hover:border-brand-400 transition-colors flex items-center gap-2"
              >
                <TrendingUp className="w-4 h-4" />
                Market Analysis
              </Link>
              <Link
                to="/blog"
                search={{ category: 'guide' }}
                className="px-4 py-2 bg-card border border-border rounded-lg hover:border-brand-400 transition-colors flex items-center gap-2"
              >
                <BookOpen className="w-4 h-4" />
                Guides
              </Link>
              <Link
                to="/blog"
                search={{ category: 'news' }}
                className="px-4 py-2 bg-card border border-border rounded-lg hover:border-brand-400 transition-colors flex items-center gap-2"
              >
                <Calendar className="w-4 h-4" />
                News
              </Link>
            </div>
          </div>
        </>
      ) : (
        <div className="text-center py-12 text-muted-foreground">
          <p>No posts yet. Check back soon!</p>
        </div>
      )}
    </div>
  )
}
