import { ScrollText } from 'lucide-react'
import { useState } from 'react'
import { Card } from '@/components/ui/Card'
import { Select } from '@/components/ui/Input'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pagination } from '@/components/ui/Pagination'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table'
import { useAsync } from '@/hooks/useAsync'
import { adminApi } from '@/services/api'
import { formatDateTime } from '@/utils/format'

const PAGE_SIZE = 25
const categories = [
  { value: '', label: 'All events' },
  { value: 'auth', label: 'Authentication' },
  { value: 'user', label: 'Profile changes' },
  { value: 'admin', label: 'Admin actions' },
  { value: 'course', label: 'Courses' },
  { value: 'section', label: 'Sections' },
  { value: 'enrollment', label: 'Enrollments' },
]

export default function AuditLogPage() {
  const [action, setAction] = useState('')
  const [page, setPage] = useState(1)

  const { data, error, loading, reload } = useAsync(
    () => adminApi.auditLogs({ action: action || undefined, page, page_size: PAGE_SIZE }),
    `audit:${action}:${page}`,
  )

  return (
    <>
      <PageHeader title="Audit Log" description="An append-only record of security and course events. Secrets are never logged." />
      <Card>
        <div className="border-b border-zinc-200 p-3">
          <Select value={action} onChange={(e) => {
              setAction(e.target.value)
              setPage(1)
            }} aria-label="Filter events" className="sm:w-56">
            {categories.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </Select>
        </div>
        {loading && !data ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : data && data.items.length === 0 ? (
          <EmptyState icon={ScrollText} title="No events" description="Nothing has been recorded for this filter yet." />
        ) : data ? (
          <>
            <Table>
              <THead>
                <tr>
                  <TH>Time</TH>
                  <TH>Actor</TH>
                  <TH>Event</TH>
                  <TH className="hidden md:table-cell">IP address</TH>
                </tr>
              </THead>
              <TBody>
                {data.items.map((entry) => (
                  <TR key={entry.id}>
                    <TD className="whitespace-nowrap text-zinc-500">{formatDateTime(entry.created_at)}</TD>
                    <TD>
                      {entry.actor_name ? (
                        <>
                          <p className="text-zinc-900">{entry.actor_name}</p>
                          <p className="text-xs text-zinc-500">{entry.actor_email}</p>
                        </>
                      ) : (
                        <span className="text-zinc-400">Deleted user</span>
                      )}
                    </TD>
                    <TD>
                      <p className="text-zinc-900">{entry.summary}</p>
                      <p className="font-mono text-xs text-zinc-400">{entry.action}</p>
                    </TD>
                    <TD className="hidden font-mono text-xs text-zinc-500 md:table-cell">{entry.ip_address ?? '—'}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />
          </>
        ) : null}
      </Card>
    </>
  )
}
