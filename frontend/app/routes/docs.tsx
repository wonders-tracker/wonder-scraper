import { createFileRoute, Link, Outlet, useLocation } from '@tanstack/react-router'
import { ArrowLeft, Book, Database, Key, Server, ShoppingCart, Activity, FileText, ExternalLink } from 'lucide-react'

export const Route = createFileRoute('/docs')({
  component: DocsLayout,
})

const DOCS_NAV = [
  {
    title: 'Getting Started',
    items: [
      { href: '/docs', label: 'Overview', icon: Book },
      { href: '/docs/authentication', label: 'Authentication', icon: Key },
    ],
  },
  {
    title: 'Cards API',
    items: [
      { href: '/docs/cards', label: 'List Cards', icon: Database },
      { href: '/docs/cards-detail', label: 'Card Detail', icon: FileText },
      { href: '/docs/cards-history', label: 'Sales History', icon: Activity },
      { href: '/docs/cards-active', label: 'Active Listings', icon: ShoppingCart },
    ],
  },
  {
    title: 'Market API',
    items: [
      { href: '/docs/market-overview', label: 'Market Overview', icon: Activity },
      { href: '/docs/market-activity', label: 'Recent Activity', icon: Activity },
      { href: '/docs/market-treatments', label: 'Treatments', icon: Database },
    ],
  },
  {
    title: 'Blokpax API',
    items: [
      { href: '/docs/blokpax-summary', label: 'Summary', icon: Server },
      { href: '/docs/blokpax-storefronts', label: 'Storefronts', icon: ShoppingCart },
      { href: '/docs/blokpax-sales', label: 'Sales', icon: Activity },
      { href: '/docs/blokpax-offers', label: 'Offers', icon: Database },
    ],
  },
]

function DocsLayout() {
  const location = useLocation()
  const currentPath = location.pathname

  return (
    <div className="min-h-screen flex">
      {/* Sidebar - Fixed with logo */}
      <aside className="w-64 border-r border-border bg-card/50 hidden md:flex flex-col fixed top-0 left-0 h-screen overflow-y-auto">
        {/* Logo Header */}
        <div className="p-4 border-b border-border">
          <Link to="/" className="flex items-center gap-2 group">
            <h1 className="text-lg font-bold tracking-tight uppercase">
              WondersTrader
            </h1>
            <span className="text-[9px] font-normal text-muted-foreground bg-muted px-1.5 py-0.5 rounded">API</span>
          </Link>
        </div>

        <div className="p-4 flex-1">
          <div className="mb-6">
            <Link
              to="/api"
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to API Portal
            </Link>
          </div>

          <nav className="space-y-6">
            {DOCS_NAV.map((section) => (
              <div key={section.title}>
                <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">
                  {section.title}
                </h3>
                <ul className="space-y-1">
                  {section.items.map((item) => {
                    const Icon = item.icon
                    const isActive = currentPath === item.href
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
        </div>

        {/* Footer Links */}
        <div className="p-4 border-t border-border text-xs text-muted-foreground">
          <div className="flex items-center gap-4">
            <Link to="/" className="hover:text-foreground transition-colors flex items-center gap-1">
              Dashboard
              <ExternalLink className="w-3 h-3" />
            </Link>
            <a
              href="https://discord.gg/Kx4fFj7V"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground transition-colors"
            >
              Discord
            </a>
          </div>
        </div>
      </aside>

      {/* Main Content - offset by sidebar width */}
      <main className="flex-1 md:ml-64 p-6 md:p-8 min-h-screen">
        <div className="max-w-4xl">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
