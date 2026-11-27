import { Activity } from 'lucide-react'
import { useState } from 'react'
import { StatusBadge } from '@/components/ui/Badge'
import { Card, CardHeader } from '@/components/ui/Card'
import { Pagination } from '@/components/ui/Pagination'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table'
import { useAsync } from '@/hooks/useAsync'
import { aiApi } from '@/services/api'
import { formatDateTime } from '@/utils/format'

const PAGE_SIZE = 15
const taskLabel: Record<string, string> = {
  capability_check: 'Capability check',
  extract_answers: 'Read script',
  evaluate_answer: 'Mark answer',
  read_question_paper: 'Read question paper',
  draft_model_answer: 'Draft model answer',
  suggest_rubric: 'Suggest rubric',
}

const tokens = (n: number | null) => (n === null ? '—' : n.toLocaleString())

export function UsageSection({ refreshKey }: { refreshKey: number }) {
  const [page, setPage] = useState(1)
  const { data, error, loading, reload } = useAsync(() => aiApi.usage(page, PAGE_SIZE), `ai-usage:${page}:${refreshKey}`)

  return (
    <Card>
      <CardHeader title="Usage" description="Every AI request made with your keys. Cost is shown when the provider reports it." />
      {loading && !data ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : data && data.total === 0 ? (
        <EmptyState icon={Activity} title="No AI requests yet" description="Requests appear here as scripts are read and marked." />
      ) : data ? (
        <>
          <div className="grid gap-px border-b border-zinc-200 bg-zinc-200 sm:grid-cols-2 lg:grid-cols-3">
            {data.summary.map((row) => (
              <div key={row.provider} className="bg-white px-5 py-3">
                <p className="text-xs font-medium tracking-wide text-zinc-500 uppercase">{row.provider}</p>
                <p className="mt-1 text-sm text-zinc-900 tabular-nums">
                  {row.requests} requests{row.failures ? ` · ${row.failures} failed` : ''}
                </p>
                <p className="text-xs text-zinc-500 tabular-nums">
                  {row.input_tokens.toLocaleString()} in · {row.output_tokens.toLocaleString()} out
                  {row.cost_usd !== null && ` · $${row.cost_usd.toFixed(4)}`}
                </p>
              </div>
            ))}
          </div>
          <Table>
            <THead>
              <tr>
                <TH>Time</TH>
                <TH>Task</TH>
                <TH className="hidden md:table-cell">Model</TH>
                <TH className="text-right">Tokens in / out</TH>
                <TH className="hidden text-right sm:table-cell">Latency</TH>
                <TH>Result</TH>
              </tr>
            </THead>
            <TBody>
              {data.items.map((entry) => (
                <TR key={entry.id}>
                  <TD className="whitespace-nowrap text-zinc-500">{formatDateTime(entry.created_at)}</TD>
                  <TD>{taskLabel[entry.task] ?? entry.task}</TD>
                  <TD className="hidden font-mono text-xs md:table-cell">
                    {entry.provider}/{entry.model}
                  </TD>
                  <TD className="text-right tabular-nums">
                    {tokens(entry.input_tokens)} / {tokens(entry.output_tokens)}
                  </TD>
                  <TD className="hidden text-right tabular-nums sm:table-cell">{(entry.latency_ms / 1000).toFixed(1)}s</TD>
                  <TD>
                    {entry.success ? (
                      <StatusBadge tone="positive">OK</StatusBadge>
                    ) : (
                      <StatusBadge tone="negative">{entry.error_code ?? 'Error'}</StatusBadge>
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
  )
}
