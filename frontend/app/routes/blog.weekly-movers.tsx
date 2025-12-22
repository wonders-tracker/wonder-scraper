import { createFileRoute, Outlet } from '@tanstack/react-router'

export const Route = createFileRoute('/blog/weekly-movers')({
  component: WeeklyMoversLayout,
})

function WeeklyMoversLayout() {
  return <Outlet />
}
