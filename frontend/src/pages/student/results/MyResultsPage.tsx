import { Award, ChevronRight } from 'lucide-react'
import { Link } from 'react-router'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { useAsync } from '@/hooks/useAsync'
import { resultsApi } from '@/services/api'
import type { StudentResultItem } from '@/types/api'
import { formatDate, formatMarks } from '@/utils/format'

export function ResultList({ items }: { items: StudentResultItem[] }) {
  return (
    <ul className="divide-y divide-zinc-100">
      {items.map((item) => (
        <li key={item.submission_id}>
          <Link to={`/student/results/${item.submission_id}`} className="flex items-center gap-4 px-5 py-3.5 hover:bg-zinc-50">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-zinc-900">{item.exam_title}</p>
              <p className="text-xs text-zinc-500">
                {item.course_code && <span className="font-mono">{item.course_code} · </span>}
                {item.provisional ? 'Awaiting teacher confirmation' : `Published ${formatDate(item.published_at)}`}
              </p>
            </div>
            {item.provisional && <Badge variant="outline">Provisional</Badge>}
            <p className="shrink-0 text-right text-sm tabular-nums">
              <span className="font-semibold text-zinc-900">{formatMarks(item.total)}</span>
              <span className="text-zinc-500"> / {formatMarks(item.max_marks)}</span>
              <span className="block text-xs text-zinc-500">{formatMarks(item.percentage)}%</span>
            </p>
            <ChevronRight className="size-4 shrink-0 text-zinc-400" aria-hidden />
          </Link>
        </li>
      ))}
    </ul>
  )
}

export default function MyResultsPage() {
  const { data, error, loading, reload } = useAsync(resultsApi.mine, 'my-results')
  return (
    <>
      <PageHeader title="My Results" description="Marks and feedback your teachers have released." />
      <Card>
        {loading && !data ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : data && data.length === 0 ? (
          <EmptyState icon={Award} title="No results yet" description="Results appear here once your teacher has reviewed and released them." />
        ) : data ? (
          <ResultList items={data} />
        ) : null}
      </Card>
    </>
  )
}
