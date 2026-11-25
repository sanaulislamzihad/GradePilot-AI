import { Navigate, Outlet, useLocation } from 'react-router'
import { LoadingState } from '@/components/ui/States'
import { useAuth } from '@/hooks/useAuth'
import { homePath, postLoginPath } from '@/layouts/navigation'
import type { UserRole } from '@/types/api'

function FullPageLoader() {
  return <LoadingState label="Loading your workspace…" className="min-h-screen" />
}

/** Signed-in users of the given role only. Others go to login or their own home. */
export function RequireRole({ role }: { role: UserRole }) {
  const { status, user } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <FullPageLoader />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (user.role !== role) return <Navigate to={homePath[user.role]} replace />
  return <Outlet />
}

/** Login and register: signed-in users go back to where they came from, or to their dashboard. */
export function GuestOnly() {
  const { status, user } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <FullPageLoader />
  if (user) return <Navigate to={postLoginPath(user.role, (location.state as { from?: string } | null)?.from)} replace />
  return <Outlet />
}
