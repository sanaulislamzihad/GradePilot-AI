import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { ChevronsUpDown, LogOut, Menu, UserCircle, X } from 'lucide-react'
import { useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router'
import { toast } from 'sonner'
import { Logo } from '@/components/Logo'
import { useAuth } from '@/hooks/useAuth'
import { homePath, navigation } from '@/layouts/navigation'
import { cn } from '@/utils/cn'
import { initials, roleLabel } from '@/utils/format'

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  if (!user) return null

  const signOut = async () => {
    await logout()
    toast.success('Signed out')
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 items-center border-b border-zinc-200 px-4">
        <Link to={homePath[user.role]} onClick={onNavigate}>
          <Logo />
        </Link>
      </div>

      <nav aria-label="Main" className="flex-1 space-y-0.5 overflow-y-auto p-3">
        <p className="px-2 pt-1 pb-2 text-[11px] font-medium tracking-wider text-zinc-400 uppercase">
          {roleLabel[user.role]}
        </p>
        {navigation[user.role].map(({ label, to, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors',
                isActive ? 'bg-zinc-900 text-white' : 'text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900',
              )
            }
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-zinc-200 p-3">
        <DropdownMenu.Root>
          <DropdownMenu.Trigger className="flex w-full items-center gap-2.5 rounded-md p-2 text-left hover:bg-zinc-100">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-zinc-200 text-xs font-semibold text-zinc-700">
              {initials(user.full_name)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium text-zinc-900">{user.full_name}</span>
              <span className="block truncate text-xs text-zinc-500">{user.email}</span>
            </span>
            <ChevronsUpDown className="size-4 text-zinc-400" aria-hidden />
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              side="top"
              align="start"
              sideOffset={6}
              className="z-50 w-56 rounded-md border border-zinc-200 bg-white p-1 shadow-md"
            >
              <DropdownMenu.Item
                onSelect={() => {
                  onNavigate?.()
                  navigate(`${homePath[user.role]}/profile`)
                }}
                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm text-zinc-700 outline-none data-highlighted:bg-zinc-100"
              >
                <UserCircle className="size-4" aria-hidden /> Profile
              </DropdownMenu.Item>
              <DropdownMenu.Separator className="my-1 h-px bg-zinc-200" />
              <DropdownMenu.Item
                onSelect={signOut}
                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm text-zinc-700 outline-none data-highlighted:bg-zinc-100"
              >
                <LogOut className="size-4" aria-hidden /> Sign out
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
    </div>
  )
}

export function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()
  const [lastPath, setLastPath] = useState(location.pathname)

  // Close the mobile drawer on any navigation, including the back button.
  if (lastPath !== location.pathname) {
    setLastPath(location.pathname)
    setMobileOpen(false)
  }

  return (
    <div className="min-h-screen bg-zinc-50/60">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r border-zinc-200 bg-white lg:block">
        <Sidebar />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-zinc-950/40" onClick={() => setMobileOpen(false)} />
          <aside className="relative h-full w-64 border-r border-zinc-200 bg-white">
            <button
              onClick={() => setMobileOpen(false)}
              className="absolute top-3.5 right-3 rounded-md p-1 text-zinc-500 hover:bg-zinc-100"
              aria-label="Close navigation"
            >
              <X className="size-5" />
            </button>
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-60">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-zinc-200 bg-white px-4 lg:hidden">
          <button
            onClick={() => setMobileOpen(true)}
            className="rounded-md p-1.5 text-zinc-600 hover:bg-zinc-100"
            aria-label="Open navigation"
          >
            <Menu className="size-5" />
          </button>
          <Logo />
        </header>
        <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
