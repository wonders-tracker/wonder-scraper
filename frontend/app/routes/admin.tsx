import { createFileRoute, redirect, Link, Outlet, useLocation } from '@tanstack/react-router'
import { auth } from '../utils/auth'
import {
  Users,
  Activity,
  BarChart3,
  Server,
  ArrowLeft,
  Eye,
  Key,
  LayoutDashboard,
} from 'lucide-react'

export const Route = createFileRoute('/admin')({
  component: AdminLayout,
  beforeLoad: () => {
    if (typeof window !== 'undefined' && !auth.isAuthenticated()) {
      throw redirect({ to: '/login' })
    }
  },
})

const ADMIN_NAV = [
  {
    title: 'Dashboard',
    items: [
      { href: '/admin', label: 'Overview', icon: LayoutDashboard },
    ],
  },
  {
    title: 'Management',
    items: [
      { href: '/admin/users', label: 'Users', icon: Users },
      { href: '/admin/scrapers', label: 'Scrapers', icon: Activity },
      { href: '/admin/api-keys', label: 'API Keys', icon: Key },
    ],
  },
  {
    title: 'Analytics',
    items: [
      { href: '/admin/analytics', label: 'Traffic', icon: Eye },
      { href: '/admin/market', label: 'Market Data', icon: BarChart3 },
    ],
  },
]

function AdminLayout() {
  const location = useLocation()
  const currentPath = location.pathname

  return (
    <div className="min-h-screen flex">
      {/* Sidebar - Fixed below all headers (promo ~32px + nav h-14 + ticker h-8 = ~120px) */}
      <aside className="w-52 border-r border-border bg-card/50 hidden md:flex flex-col fixed top-[120px] bottom-0 left-0">
        {/* Header - compact */}
        <div className="px-3 py-2 border-b border-border flex items-center gap-2 shrink-0">
          <Server className="w-4 h-4 text-primary" />
          <span className="text-sm font-bold">Admin</span>
        </div>

        {/* Navigation - scrollable */}
        <div className="p-2 flex-1 overflow-y-auto">
          <nav className="space-y-4">
            {ADMIN_NAV.map((section) => (
              <div key={section.title}>
                <h3 className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-2 px-2">
                  {section.title}
                </h3>
                <ul className="space-y-0.5">
                  {section.items.map((item) => {
                    const Icon = item.icon
                    const isActive = currentPath === item.href ||
                      (item.href !== '/admin' && currentPath.startsWith(item.href))
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

        {/* Footer */}
        <div className="p-3 border-t border-border">
          <Link
            to="/"
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors px-2 py-1.5"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </Link>
        </div>
      </aside>

      {/* Mobile Header - shown on small screens */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-50 bg-card border-b border-border p-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Server className="w-5 h-5 text-primary" />
            <span className="font-bold">Admin</span>
          </div>
          <Link to="/" className="text-sm text-muted-foreground">
            ← Dashboard
          </Link>
        </div>
        {/* Mobile nav tabs */}
        <div className="flex gap-1 mt-3 overflow-x-auto pb-1">
          {ADMIN_NAV.flatMap(section => section.items).map((item) => {
            const Icon = item.icon
            const isActive = currentPath === item.href ||
              (item.href !== '/admin' && currentPath.startsWith(item.href))
            return (
              <Link
                key={item.href}
                to={item.href}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-full whitespace-nowrap transition-colors ${
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted/50 text-muted-foreground'
                }`}
              >
                <Icon className="w-3 h-3" />
                {item.label}
              </Link>
            )
          })}
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 md:ml-52 pt-24 md:pt-0 min-h-screen">
        <Outlet />
      </main>
    </div>
  )
}
