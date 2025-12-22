import { createFileRoute, Link, Outlet, useLocation } from '@tanstack/react-router'
import { TrendingUp, Newspaper, BookOpen, Calendar } from 'lucide-react'

export const Route = createFileRoute('/blog')({
  component: BlogLayout,
})

const BLOG_NAV = [
  {
    title: 'Content',
    items: [
      { href: '/blog', label: 'Latest Posts', icon: Newspaper },
      { href: '/blog/weekly-movers', label: 'Weekly Movers', icon: TrendingUp },
    ],
  },
  {
    title: 'Categories',
    items: [
      { href: '/blog?category=analysis', label: 'Market Analysis', icon: TrendingUp },
      { href: '/blog?category=news', label: 'News & Updates', icon: Newspaper },
      { href: '/blog?category=guide', label: 'Guides', icon: BookOpen },
    ],
  },
]

function BlogLayout() {
  const location = useLocation()
  const currentPath = location.pathname

  return (
    <div className="min-h-screen flex">
      {/* Sidebar - Fixed below main nav */}
      <aside className="w-64 border-r border-border bg-card/50 hidden md:flex flex-col fixed top-[104px] left-0 bottom-14 overflow-y-auto">
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
                      (item.href === '/blog/weekly-movers' && currentPath.startsWith('/blog/weekly-movers'))
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
              <Calendar className="w-4 h-4" />
              RSS Feed
            </a>
          </div>
        </div>
      </aside>

      {/* Main Content - offset by sidebar width */}
      <main className="flex-1 md:ml-64 p-6 md:p-8 min-h-screen pb-20">
        <div className="max-w-4xl mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
