import { createContext, useContext, useState, ReactNode } from 'react'

type TimePeriodContextType = {
  timePeriod: string
  setTimePeriod: (period: string) => void
}

const TimePeriodContext = createContext<TimePeriodContextType | undefined>(undefined)

export function TimePeriodProvider({ children }: { children: ReactNode }) {
  const [timePeriod, setTimePeriod] = useState<string>('7d')
  return (
    <TimePeriodContext.Provider value={{ timePeriod, setTimePeriod }}>
      {children}
    </TimePeriodContext.Provider>
  )
}

export function useTimePeriod() {
  const context = useContext(TimePeriodContext)
  if (!context) {
    throw new Error('useTimePeriod must be used within TimePeriodProvider')
  }
  return context
}
