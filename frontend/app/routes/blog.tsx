import { createFileRoute, Link, Outlet, useLocation } from '@tanstack/react-router'
import { TrendingUp, Newspaper, BookOpen, Rss, BarChart2 } from 'lucide-react'

export const Route = createFileRoute('/blog')({
  component: BlogLayout,
})

const BLOG_NAV = [
  {
    title: 'Browse',
    items: [
      { href: '/blog', label: 'All Posts', icon: Newspaper },
      { href: '/blog/weekly-movers', label: 'Weekly Reports', icon: TrendingUp },
      { href: '/blog/market-insights', label: 'Market Insights', icon: BarChart2 },
    ],
  },
  {
    title: 'Categories',
    items: [
      { href: '/blog?category=analysis', label: 'Market Analysis', icon: TrendingUp },
      { href: '/blog?category=guide', label: 'Guides', icon: BookOpen },
      { href: '/blog?category=news', label: 'News', icon: Newspaper },
    ],
  },
]

// Mobile navigation items (flat list for horizontal scroll)
const MOBILE_NAV = [
  { href: '/blog', label: 'All', icon: Newspaper },
  { href: '/blog/weekly-movers', label: 'Weekly', icon: TrendingUp },
  { href: '/blog/market-insights', label: 'Insights', icon: BarChart2 },
]

function BlogLayout() {
  const location = useLocation()
  const currentPath = location.pathname

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      {/* Mobile Navigation - horizontal scroll (below nav h-14 + ticker h-8 = 5.5rem) */}
      <div className="md:hidden border-b border-border bg-card/50 sticky top-[5.5rem] z-30">
        <div className="flex items-center gap-1 p-2 overflow-x-auto scrollbar-none">
          {MOBILE_NAV.map((item) => {
            const Icon = item.icon
            const isActive = currentPath === item.href ||
              (item.href === '/blog/weekly-movers' && currentPath.startsWith('/blog/weekly-movers')) ||
              (item.href === '/blog/market-insights' && currentPath.startsWith('/blog/market-insights'))
            return (
              <Link
                key={item.href}
                to={item.href}
                className={`flex items-center gap-1.5 px-3 py-2 text-sm rounded-full whitespace-nowrap transition-colors ${
                  isActive
                    ? 'bg-primary text-primary-foreground font-medium'
                    : 'bg-muted text-muted-foreground hover:text-foreground'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {item.label}
              </Link>
            )
          })}
        </div>
      </div>

      {/* Desktop Sidebar (below nav h-14 + ticker h-8 = 5.5rem, above footer h-10 = 2.5rem) */}
      <aside className="w-64 border-r border-border bg-card/50 hidden md:flex flex-col fixed top-[5.5rem] left-0 bottom-10 overflow-y-auto">
        <div className="p-4 flex-1">
          <nav className="space-y-6">
            {BLOG_NAV.map((section) => (
              <div key={section.title}>
                <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">
                  {section.title}
                </h3>
                <ul className="space-y-1">
                  {section.items.map((item) => {
                    const Icon = item.icon
                    const isActive = currentPath === item.href ||
                      (item.href === '/blog/weekly-movers' && currentPath.startsWith('/blog/weekly-movers')) ||
                      (item.href === '/blog/market-insights' && currentPath.startsWith('/blog/market-insights'))
                    return (
                      <li key={item.href}>
                        <Link
                          to={item.href}
                          className={`flex items-center gap-2 px-3 py-2 text-sm rounded-md transition-colors ${
                            isActive
                              ? 'bg-primary/10 text-primary font-medium'
                              : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                          }`}
                        >
                          <Icon className="w-4 h-4" />
                          {item.label}
                        </Link>
                      </li>
                    )
                  })}
                </ul>
              </div>
            ))}
          </nav>

          {/* RSS Feed Link */}
          <div className="mt-8 pt-4 border-t border-border">
            <a
              href="/feed.xml"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <Rss className="w-4 h-4" />
              RSS Feed
            </a>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 md:ml-64 p-4 sm:p-6 md:p-8 min-h-screen pb-20">
        <Outlet />
      </main>
    </div>
  )
}
