import { Outlet, createRootRoute, Link } from '@tanstack/react-router'
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'
import { LayoutDashboard, LineChart, Wallet, Settings, User, Server, LogOut } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api, auth } from '../utils/auth'
import { useState } from 'react'

type UserProfile = {
    id: number
    email: string
    is_superuser: boolean
}

export const Route = createRootRoute({
  component: RootComponent,
})

function RootComponent() {
  const { data: user } = useQuery({
      queryKey: ['me'],
      queryFn: async () => {
          try {
              return await api.get('users/me').json<UserProfile>()
          } catch {
              // If API fails (e.g. 401), clear local token so app knows we are logged out
              // This prevents redirect loops where localStorage has token but API rejects it
              localStorage.removeItem('token')
              return null
          }
      },
      retry: false
  })

  return (
    <div className="min-h-screen bg-background text-foreground antialiased font-mono flex flex-col">
             {/* Top Header Navigation */}
             <div className="h-16 border-b border-border sticky top-0 bg-background/95 backdrop-blur z-50 flex items-center px-6 justify-between">
               <div className="flex items-center gap-8">
                    <h1 className="text-xl font-bold tracking-tight uppercase flex items-center gap-2">
                WondersTracker 
                <span className="text-[10px] font-normal text-muted-foreground bg-muted px-1.5 py-0.5 rounded">BETA</span>
             </h1>

             <nav className="hidden md:flex items-center gap-1">
                <Link to="/" className="flex items-center gap-2 px-4 py-2 text-muted-foreground hover:text-foreground rounded-md transition-colors text-xs font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5">
                    <LayoutDashboard className="w-4 h-4" />
                    <span>Dashboard</span>
                </Link>
                <Link to="/market" className="flex items-center gap-2 px-4 py-2 text-muted-foreground hover:text-foreground rounded-md transition-colors text-xs font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5">
                    <LineChart className="w-4 h-4" />
                    <span>Market</span>
                </Link>
                {user && (
                    <>
                        <Link to="/portfolio" className="flex items-center gap-2 px-4 py-2 text-muted-foreground hover:text-foreground rounded-md transition-colors text-xs font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5">
                            <Wallet className="w-4 h-4" />
                            <span>Portfolio</span>
                        </Link>
                        <Link to="/profile" className="flex items-center gap-2 px-4 py-2 text-muted-foreground hover:text-foreground rounded-md transition-colors text-xs font-bold uppercase [&.active]:text-primary [&.active]:bg-primary/5">
                            <User className="w-4 h-4" />
                            <span>Profile</span>
                        </Link>
                    </>
                )}
             </nav>
        </div>

        <div className="flex items-center gap-6">
            {/* System Status */}
             <div className="hidden md:flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                <span className="text-[10px] text-muted-foreground uppercase font-bold">System Online</span>
            </div>

             {/* Admin Quick Links */}
            {user?.is_superuser && (
                 <div className="hidden md:flex items-center gap-2 border-r border-border pr-6 mr-2">
                    <a href="#" className="text-muted-foreground hover:text-foreground transition-colors" title="Scraper Status">
                        <Server className="w-4 h-4" />
                    </a>
                    <a href="#" className="text-muted-foreground hover:text-foreground transition-colors" title="Settings">
                        <Settings className="w-4 h-4" />
                    </a>
                 </div>
            )}

            {user ? (
                <div className="flex items-center gap-4">
                    <div className="text-xs font-bold uppercase truncate max-w-[120px] hidden sm:block">{user.email}</div>
                    <button onClick={() => auth.logout()} className="text-muted-foreground hover:text-red-500 transition-colors p-1" title="Logout">
                        <LogOut className="w-4 h-4" />
                    </button>
                </div>
            ) : (
                <a href="/login" className="text-xs font-bold uppercase px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90 transition-colors relative z-50">
                    Login
                </a>
            )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <div className="flex-1 overflow-y-auto bg-background scrollbar-hide">
            <Outlet />
          </div>
      </div>
      
      <TanStackRouterDevtools />
    </div>
  )
}
