import type { ReactNode } from 'react'
import { RefreshCw } from 'lucide-react'
import { StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { ErrorState, LoadingState } from '@/components/ui/States'
import { useAsync } from '@/hooks/useAsync'
import { adminApi } from '@/services/api'
import { formatDuration } from '@/utils/format'

export default function SystemPage() {
  const { data, error, loading, reload } = useAsync(adminApi.system, 'admin-system')

  const rows: [string, ReactNode][] = data
    ? [
        ['Overall', <StatusBadge tone={data.status === 'ok' ? 'positive' : 'warning'}>{data.status === 'ok' ? 'Healthy' : 'Degraded'}</StatusBadge>],
        ['Database', <StatusBadge tone={data.database_ok ? 'positive' : 'negative'}>{data.database_ok ? `Connected (${data.database_backend})` : 'Unavailable'}</StatusBadge>],
        ['File storage', <StatusBadge tone={data.storage_writable ? 'positive' : 'negative'}>{data.storage_writable ? 'Writable' : 'Not writable'}</StatusBadge>],
        ['Schema revision', <code className="font-mono text-xs">{data.migration_revision ?? 'unknown'}</code>],
        ['API version', data.version],
        ['Environment', data.environment],
        ['API uptime', formatDuration(data.uptime_seconds)],
        ['Active sessions', <span className="tabular-nums">{data.active_sessions}</span>],
      ]
    : []

  return (
    <>
      <PageHeader
        title="System"
        description="Live health of the API, database and file storage."
        actions={
          <Button variant="secondary" onClick={reload} loading={loading && !!data}>
            <RefreshCw /> Refresh
          </Button>
        }
      />
      {loading && !data ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : (
        <Card className="max-w-2xl">
          <CardHeader title="Status" />
          <dl className="divide-y divide-zinc-100">
            {rows.map(([label, value]) => (
              <div key={label} className="flex items-center justify-between gap-4 px-5 py-3">
                <dt className="text-sm text-zinc-500">{label}</dt>
                <dd className="text-sm text-zinc-900">{value}</dd>
              </div>
            ))}
          </dl>
        </Card>
      )}
    </>
  )
}
