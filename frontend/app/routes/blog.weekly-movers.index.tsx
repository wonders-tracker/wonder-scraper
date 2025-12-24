import { createFileRoute, Link } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { Calendar, ArrowRight } from 'lucide-react'

export const Route = createFileRoute('/blog/weekly-movers/')({
  component: WeeklyMoversArchivePage,
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

function parseWeekFromSlug(slug: string): { weekStart: Date; weekEnd: Date } | null {
  // Extract date from slug like "weekly-movers-2024-12-22"
  const match = slug.match(/weekly-movers-(\d{4}-\d{2}-\d{2})/)
  if (!match) return null

  const weekEnd = new Date(match[1] + 'T00:00:00Z')
  const weekStart = new Date(weekEnd)
  weekStart.setDate(weekStart.getDate() - 6)

  return { weekStart, weekEnd }
}

function WeeklyMoversArchivePage() {
  const { data: allPosts, isLoading } = useQuery<BlogPost[]>({
    queryKey: ['blog-posts'],
    queryFn: async () => {
      const res = await fetch('/blog-manifest.json')
      if (!res.ok) return []
      return res.json()
    },
    staleTime: 60 * 60 * 1000,
  })

  // Filter to only weekly movers posts
  const weeklyPosts = allPosts?.filter(post =>
    post.tags?.includes('weekly-movers')
  ) || []

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <header>
        <h1 className="text-3xl md:text-4xl font-bold font-serif mb-3">Weekly Market Reports</h1>
        <p className="text-lg text-muted-foreground">
          Weekly analysis of price movements, top gainers, losers, and market trends for Wonders of the First TCG.
        </p>
      </header>

      {isLoading ? (
        <div className="space-y-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="animate-pulse bg-card border border-border rounded-xl p-6">
              <div className="h-6 bg-muted rounded w-2/3 mb-3" />
              <div className="h-4 bg-muted rounded w-full" />
            </div>
          ))}
        </div>
      ) : weeklyPosts.length > 0 ? (
        <div className="space-y-4">
          {weeklyPosts.map((post) => {
            const dates = parseWeekFromSlug(post.slug)
            const weekLabel = dates
              ? `${dates.weekStart.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - ${dates.weekEnd.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`
              : post.title

            return (
              <Link
                key={post.slug}
                to="/blog/$slug"
                params={{ slug: post.slug }}
                className="group block bg-card border border-border rounded-xl p-6 hover:border-brand-400/50 transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                      <Calendar className="w-4 h-4 text-brand-400" />
                      <span>{weekLabel}</span>
                    </div>
                    <h2 className="text-lg font-semibold group-hover:text-brand-400 transition-colors mb-2">
                      {post.title}
                    </h2>
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {post.description}
                    </p>
                  </div>
                  <ArrowRight className="w-5 h-5 text-muted-foreground group-hover:text-brand-400 transition-colors flex-shrink-0 mt-1" />
                </div>
              </Link>
            )
          })}
        </div>
      ) : (
        <div className="bg-muted/30 rounded-xl p-8 text-center">
          <p className="text-muted-foreground">No weekly reports available yet.</p>
          <p className="mt-2 text-sm text-muted-foreground">Check back after the first week of market tracking.</p>
        </div>
      )}

      <footer className="pt-8 border-t border-border">
        <p className="text-sm text-muted-foreground">
          Weekly reports are published every Sunday, covering the previous 7 days of market activity.
          All data is sourced from completed sales on eBay and Blokpax.
        </p>
      </footer>
    </div>
  )
}
