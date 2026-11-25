import { Activity } from 'lucide-react'
import { EmptyState } from '@/components/ui/States'
import type { ActivityItem } from '@/types/api'
import { formatDateTime, formatRelative } from '@/utils/format'

export function ActivityList({ items }: { items: ActivityItem[] }) {
  if (items.length === 0) {
    return <EmptyState icon={Activity} title="No activity yet" description="Your actions will be listed here." />
  }
  return (
    <ul className="divide-y divide-zinc-100">
      {items.map((item) => (
        <li key={item.id} className="flex items-center justify-between gap-4 px-5 py-3">
          <span className="text-sm text-zinc-700">{item.summary}</span>
          <time dateTime={item.created_at} title={formatDateTime(item.created_at)} className="shrink-0 text-xs text-zinc-400">
            {formatRelative(item.created_at)}
          </time>
        </li>
      ))}
    </ul>
  )
}
