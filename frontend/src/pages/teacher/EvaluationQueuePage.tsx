import { CheckCheck, ClipboardCheck } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { toast } from 'sonner'
import { StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/Dialog'
import { Select } from '@/components/ui/Input'
import { PageHeader } from '@/components/ui/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table'
import { useAsync } from '@/hooks/useAsync'
import { examApi, reviewApi } from '@/services/api'
import type { ReviewStatus } from '@/types/api'
import { formatMarks } from '@/utils/format'
import { flagText, needsAttention, reviewStatusLabel, verificationLabel } from '@/utils/reviewFlags'

export default function EvaluationQueuePage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const examId = params.get('exam') ?? ''
  const status = (params.get('status') ?? 'pending') as ReviewStatus | 'all'
  const flaggedOnly = params.get('flagged') === '1'
  const [confirming, setConfirming] = useState(false)

  const exams = useAsync(() => examApi.list({ status: 'published', page_size: 100 }), 'queue-exams')
  const { data, error, loading, reload } = useAsync(
    () =>
      reviewApi.queue({
        exam_id: examId || undefined,
        review_status: status === 'all' ? undefined : status,
        flagged_only: flaggedOnly || undefined,
      }),
    `review-queue:${examId}:${status}:${flaggedOnly}`,
  )

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }
  const clean = data?.filter((i) => i.review_status === 'pending' && !needsAttention(i.flags) && i.final_total !== null).length ?? 0

  return (
    <>
      <PageHeader
        title="AI Evaluation"
        description="Review AI-suggested marks. Evaluations with flags need your attention first; nothing reaches students until you approve and publish."
        actions={
          examId && (
            <Button variant="secondary" onClick={() => setConfirming(true)} disabled={clean === 0}>
              <CheckCheck /> Approve all without flags ({clean})
            </Button>
          )
        }
      />
      <Card>
        <div className="flex flex-col gap-2 border-b border-zinc-200 p-3 lg:flex-row lg:items-center">
          <Select value={examId} onChange={(e) => setFilter('exam', e.target.value)} aria-label="Filter by exam" className="lg:w-72">
            <option value="">All exams</option>
            {exams.data?.items.map((exam) => (
              <option key={exam.id} value={exam.id}>
                {exam.title}
                {exam.course_code ? ` (${exam.course_code})` : ''}
              </option>
            ))}
          </Select>
          <Select value={status} onChange={(e) => setFilter('status', e.target.value === 'pending' ? '' : e.target.value)} aria-label="Filter by review status" className="lg:w-48">
            <option value="pending">Awaiting review</option>
            <option value="approved">Approved</option>
            <option value="all">All</option>
          </Select>
          <label className="flex items-center gap-2 px-1 text-sm text-zinc-700">
            <input type="checkbox" className="accent-zinc-900" checked={flaggedOnly} onChange={(e) => setFilter('flagged', e.target.checked ? '1' : '')} />
            Flagged only
          </label>
        </div>

        {loading && !data ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : data && data.length === 0 ? (
          <EmptyState
            icon={ClipboardCheck}
            title={status === 'pending' ? 'Nothing waiting for review' : 'No evaluations'}
            description="Marked submissions appear here once AI evaluation finishes."
          />
        ) : data ? (
          <Table>
            <THead>
              <tr>
                <TH>Student</TH>
                <TH className="hidden md:table-cell">Exam</TH>
                <TH className="text-right">Marks</TH>
                <TH>Needs attention</TH>
                <TH className="hidden lg:table-cell">Checks</TH>
                <TH>Review</TH>
              </tr>
            </THead>
            <TBody>
              {data.map((item) => {
                const attention = item.flags.filter((f) => f !== 'missing_answer')
                return (
                  <TR key={item.evaluation_id} className="cursor-pointer" onClick={() => navigate(`/teacher/submissions/${item.submission_id}`)}>
                    <TD>
                      <Link to={`/teacher/submissions/${item.submission_id}`} onClick={(e) => e.stopPropagation()} className="font-medium text-zinc-900 hover:underline">
                        {item.student_name}
                      </Link>
                      <p className="font-mono text-xs text-zinc-500">
                        {item.student_number} · {item.submission_code}
                      </p>
                    </TD>
                    <TD className="hidden md:table-cell">{item.exam_title}</TD>
                    <TD className="text-right tabular-nums">
                      <span className="font-medium text-zinc-900">{item.final_total === null ? '—' : formatMarks(item.final_total)}</span>
                      <span className="text-zinc-500"> / {formatMarks(item.total_max)}</span>
                      {item.final_total !== item.total_awarded && (
                        <p className="text-xs text-zinc-400">AI {item.total_awarded === null ? '—' : formatMarks(item.total_awarded)}</p>
                      )}
                    </TD>
                    <TD>
                      {attention.length ? (
                        <span className="text-[13px] text-amber-800">
                          {flagText[attention[0]!] ?? attention[0]}
                          {attention.length > 1 && <span className="text-zinc-500"> +{attention.length - 1}</span>}
                        </span>
                      ) : (
                        <span className="text-[13px] text-zinc-400">None</span>
                      )}
                    </TD>
                    <TD className="hidden text-[13px] text-zinc-600 lg:table-cell">{verificationLabel[item.verification_status]}</TD>
                    <TD>
                      <StatusBadge tone={item.review_status === 'approved' ? 'positive' : attention.length ? 'warning' : 'muted'}>
                        {reviewStatusLabel[item.review_status]}
                      </StatusBadge>
                    </TD>
                  </TR>
                )
              })}
            </TBody>
          </Table>
        ) : null}
      </Card>

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={`Approve ${clean} evaluation${clean === 1 ? '' : 's'} without flags?`}
        description="Only evaluations with no review flags and a complete total are approved. You can still reopen any of them before results are published."
        confirmLabel="Approve"
        onConfirm={async () => {
          const result = await reviewApi.approveUnflagged(examId)
          toast.success(`${result.approved} approved${result.skipped ? `, ${result.skipped} left for review` : ''}`)
          reload()
        }}
      />
    </>
  )
}
