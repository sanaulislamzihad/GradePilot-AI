import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { MoreHorizontal, Search, Users } from 'lucide-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { toast } from 'sonner'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/Dialog'
import { Input, Select } from '@/components/ui/Input'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pagination } from '@/components/ui/Pagination'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table'
import { useAsync } from '@/hooks/useAsync'
import { useAuth } from '@/hooks/useAuth'
import { useDebounced } from '@/hooks/useDebounced'
import { adminApi } from '@/services/api'
import type { User, UserRole } from '@/types/api'
import { formatDate, formatDateTime, roleLabel } from '@/utils/format'

const PAGE_SIZE = 20
const roles: UserRole[] = ['teacher', 'student', 'admin']

type Change = { user: User; role?: UserRole; is_active?: boolean } | null

const menuItem =
  'flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm text-zinc-700 outline-none data-highlighted:bg-zinc-100 data-disabled:pointer-events-none data-disabled:opacity-40'

function describeChange(change: NonNullable<Change>) {
  if (change.is_active === false) return { title: `Deactivate ${change.user.full_name}?`, body: 'They are signed out everywhere and cannot sign in until reactivated.', label: 'Deactivate', destructive: true }
  if (change.is_active === true) return { title: `Reactivate ${change.user.full_name}?`, body: 'They will be able to sign in again.', label: 'Reactivate', destructive: false }
  return {
    title: `Make ${change.user.full_name} ${change.role === 'admin' ? 'an' : 'a'} ${roleLabel[change.role!].toLowerCase()}?`,
    body: 'Their current sessions end immediately and they see the new role after signing in again.',
    label: 'Change role',
    destructive: false,
  }
}

export default function UsersPage() {
  const { user: me } = useAuth()
  const [params, setParams] = useSearchParams()
  const roleFilter = (params.get('role') as UserRole | null) ?? undefined
  const statusFilter = params.get('status') ?? ''
  const [query, setQuery] = useState('')
  const debouncedQuery = useDebounced(query, 300)
  const [page, setPage] = useState(1)
  const [change, setChange] = useState<Change>(null)

  const { data, error, loading, reload, setData } = useAsync(
    () =>
      adminApi.users({
        q: debouncedQuery || undefined,
        role: roleFilter,
        is_active: statusFilter ? statusFilter === 'active' : undefined,
        page,
        page_size: PAGE_SIZE,
      }),
    `users:${debouncedQuery}:${roleFilter ?? ''}:${statusFilter}:${page}`,
  )

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
    setPage(1)
  }

  const dialog = change ? describeChange(change) : null

  return (
    <>
      <PageHeader title="Users" description="Search accounts, change roles and control access." />
      <Card>
        <div className="flex flex-col gap-2 border-b border-zinc-200 p-3 sm:flex-row">
          <div className="relative flex-1 sm:max-w-xs">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-zinc-400" aria-hidden />
            <Input type="search" value={query} onChange={(e) => {
                setQuery(e.target.value)
                setPage(1)
              }} placeholder="Name, email or student ID" aria-label="Search users" className="pl-9" />
          </div>
          <Select value={roleFilter ?? ''} onChange={(e) => setFilter('role', e.target.value)} aria-label="Filter by role" className="sm:w-40">
            <option value="">All roles</option>
            {roles.map((role) => (
              <option key={role} value={role}>
                {roleLabel[role]}
              </option>
            ))}
          </Select>
          <Select value={statusFilter} onChange={(e) => setFilter('status', e.target.value)} aria-label="Filter by status" className="sm:w-40">
            <option value="">Any status</option>
            <option value="active">Active</option>
            <option value="inactive">Deactivated</option>
          </Select>
        </div>

        {loading && !data ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : data && data.items.length === 0 ? (
          <EmptyState icon={Users} title="No users found" description="Try a different search or filter." />
        ) : data ? (
          <>
            <Table>
              <THead>
                <tr>
                  <TH>User</TH>
                  <TH>Role</TH>
                  <TH>Status</TH>
                  <TH className="hidden lg:table-cell">Last sign-in</TH>
                  <TH className="hidden md:table-cell">Joined</TH>
                  <TH className="w-12">
                    <span className="sr-only">Actions</span>
                  </TH>
                </tr>
              </THead>
              <TBody>
                {data.items.map((u) => (
                  <TR key={u.id}>
                    <TD>
                      <p className="font-medium text-zinc-900">
                        {u.full_name} {u.id === me?.id && <span className="text-xs font-normal text-zinc-400">(you)</span>}
                      </p>
                      <p className="text-xs text-zinc-500">
                        {u.email}
                        {u.student_id && <span className="font-mono"> · {u.student_id}</span>}
                      </p>
                    </TD>
                    <TD>
                      <Badge variant={u.role === 'admin' ? 'solid' : 'neutral'}>{roleLabel[u.role]}</Badge>
                    </TD>
                    <TD>
                      <StatusBadge tone={u.is_active ? 'positive' : 'negative'}>{u.is_active ? 'Active' : 'Deactivated'}</StatusBadge>
                    </TD>
                    <TD className="hidden text-zinc-500 lg:table-cell">{u.last_login_at ? formatDateTime(u.last_login_at) : 'Never'}</TD>
                    <TD className="hidden text-zinc-500 md:table-cell">{formatDate(u.created_at)}</TD>
                    <TD>
                      {u.id !== me?.id && (
                        <DropdownMenu.Root>
                          <DropdownMenu.Trigger asChild>
                            <Button variant="ghost" size="icon" aria-label={`Actions for ${u.full_name}`}>
                              <MoreHorizontal />
                            </Button>
                          </DropdownMenu.Trigger>
                          <DropdownMenu.Portal>
                            <DropdownMenu.Content align="end" sideOffset={4} className="z-50 w-52 rounded-md border border-zinc-200 bg-white p-1 shadow-md">
                              <DropdownMenu.Label className="px-2 py-1 text-xs text-zinc-400">Change role</DropdownMenu.Label>
                              {roles.map((role) => (
                                <DropdownMenu.Item
                                  key={role}
                                  className={menuItem}
                                  disabled={role === u.role || (role === 'student' && !u.student_id)}
                                  onSelect={() => setChange({ user: u, role })}
                                >
                                  {roleLabel[role]}
                                  {role === 'student' && !u.student_id && <span className="ml-auto text-xs text-zinc-400">No ID</span>}
                                </DropdownMenu.Item>
                              ))}
                              <DropdownMenu.Separator className="my-1 h-px bg-zinc-200" />
                              <DropdownMenu.Item
                                className={`${menuItem} ${u.is_active ? 'text-red-700 data-highlighted:bg-red-50' : ''}`}
                                onSelect={() => setChange({ user: u, is_active: !u.is_active })}
                              >
                                {u.is_active ? 'Deactivate account' : 'Reactivate account'}
                              </DropdownMenu.Item>
                            </DropdownMenu.Content>
                          </DropdownMenu.Portal>
                        </DropdownMenu.Root>
                      )}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />
          </>
        ) : null}
      </Card>

      <ConfirmDialog
        open={change !== null}
        onOpenChange={(open) => !open && setChange(null)}
        title={dialog?.title ?? ''}
        description={dialog?.body ?? ''}
        confirmLabel={dialog?.label ?? 'Confirm'}
        destructive={dialog?.destructive}
        onConfirm={async () => {
          if (!change) return
          const { user, ...payload } = change
          const updated = await adminApi.updateUser(user.id, payload)
          setData((current) => (current ? { ...current, items: current.items.map((u) => (u.id === updated.id ? updated : u)) } : current))
          toast.success(`${updated.full_name} updated`)
        }}
      />
    </>
  )
}
