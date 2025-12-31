import { createContext, useContext, ReactNode } from 'react'

export type CurrentUser = {
  id: number
  email: string
  username?: string
  discord_handle?: string
  is_superuser?: boolean
  onboarding_completed?: boolean
  subscription_tier?: string
  is_pro?: boolean
}

type UserContextValue = {
  user: CurrentUser | null
  isLoading: boolean
}

const UserContext = createContext<UserContextValue | undefined>(undefined)

type UserProviderProps = UserContextValue & {
  children: ReactNode
}

export function UserProvider({ user, isLoading, children }: UserProviderProps) {
  return (
    <UserContext.Provider value={{ user, isLoading }}>
      {children}
    </UserContext.Provider>
  )
}

export function useCurrentUser() {
  const context = useContext(UserContext)
  if (!context) {
    throw new Error('useCurrentUser must be used within a UserProvider')
  }
  return context
}
