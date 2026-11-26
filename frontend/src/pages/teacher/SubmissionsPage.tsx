import { Inbox, Search } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { SubmissionStatusBadge } from '@/components/SubmissionStatusBadge'
import { Card } from '@/components/ui/Card'
import { Input, Select } from '@/components/ui/Input'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pagination } from '@/components/ui/Pagination'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table'
import { useAsync } from '@/hooks/useAsync'
import { useDebounced } from '@/hooks/useDebounced'
import { examApi, submissionApi } from '@/services/api'
import type { SubmissionStatus } from '@/types/api'
import { formatDateTime } from '@/utils/format'
import { submissionStatusLabel } from '@/utils/submissionStatus'

const PAGE_SIZE = 20
const STATUSES: SubmissionStatus[] = [
  'uploaded',
  'queued',
  'extracting',
  'ocr_review_required',
  'ready_for_evaluation',
  'evaluating',
  'verifying',
  'teacher_review_required',
  'approved',
  'published',
  'failed',
]

export default function SubmissionsPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const examId = params.get('exam') ?? ''
  const status = (params.get('status') ?? '') as SubmissionStatus | ''
  const [query, setQuery] = useState('')
  const debouncedQuery = useDebounced(query, 300)
  const [page, setPage] = useState(1)

  const exams = useAsync(() => examApi.list({ status: 'published', page_size: 100 }), 'submission-filter-exams')
  const { data, error, loading, reload } = useAsync(
    () =>
      submissionApi.list({
        exam_id: examId || undefined,
        status: status || undefined,
        q: debouncedQuery || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
    `teacher-submissions:${examId}:${status}:${debouncedQuery}:${page}`,
  )

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
    setPage(1)
  }
  const filtered = Boolean(examId || status || debouncedQuery)

  return (
    <>
      <PageHeader title="Submissions" description="Each student's current answer script for your published exams." />
      <Card>
        <div className="flex flex-col gap-2 border-b border-zinc-200 p-3 lg:flex-row">
          <Select value={examId} onChange={(e) => setFilter('exam', e.target.value)} aria-label="Filter by exam" className="lg:w-72">
            <option value="">All exams</option>
            {exams.data?.items.map((exam) => (
              <option key={exam.id} value={exam.id}>
                {exam.title}
                {exam.course_code ? ` (${exam.course_code})` : ''}
              </option>
            ))}
          </Select>
          <Select value={status} onChange={(e) => setFilter('status', e.target.value)} aria-label="Filter by status" className="lg:w-52">
            <option value="">Any status</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {submissionStatusLabel(s)}
              </option>
            ))}
          </Select>
          <div className="relative flex-1 lg:max-w-xs">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-zinc-400" aria-hidden />
            <Input
              type="search"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setPage(1)
              }}
              placeholder="Student name, ID or submission ID"
              aria-label="Search submissions"
              className="pl-9"
            />
          </div>
        </div>

        {loading && !data ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : data && data.items.length === 0 ? (
          <EmptyState
            icon={filtered ? Search : Inbox}
            title={filtered ? 'No matching submissions' : 'No submissions yet'}
            description={filtered ? 'Try a different exam, status or search.' : 'Scripts appear here as soon as students submit them.'}
          />
        ) : data ? (
          <>
            <Table>
              <THead>
                <tr>
                  <TH>Student</TH>
                  <TH className="hidden md:table-cell">Exam</TH>
                  <TH>Submission</TH>
                  <TH className="hidden lg:table-cell">Submitted</TH>
                  <TH>Status</TH>
                </tr>
              </THead>
              <TBody>
                {data.items.map((s) => (
                  <TR key={s.id} className="cursor-pointer" onClick={() => navigate(`/teacher/submissions/${s.id}`)}>
                    <TD>
                      <Link to={`/teacher/submissions/${s.id}`} onClick={(e) => e.stopPropagation()} className="font-medium text-zinc-900 hover:underline">
                        {s.student.full_name}
                      </Link>
                      <p className="font-mono text-xs text-zinc-500">{s.student.student_number}</p>
                    </TD>
                    <TD className="hidden md:table-cell">
                      <p className="text-zinc-900">{s.exam_title}</p>
                      {s.course_code && (
                        <p className="text-xs text-zinc-500">
                          <span className="font-mono">{s.course_code}</span>
                          {s.section_name && ` · Section ${s.section_name}`}
                        </p>
                      )}
                    </TD>
                    <TD>
                      <p className="font-mono text-zinc-900">{s.code}</p>
                      <p className="text-xs text-zinc-500">
                        Attempt {s.attempt_number} · {s.page_count} page{s.page_count === 1 ? '' : 's'}
                      </p>
                    </TD>
                    <TD className="hidden whitespace-nowrap text-zinc-500 lg:table-cell">{formatDateTime(s.submitted_at)}</TD>
                    <TD>
                      <SubmissionStatusBadge status={s.status} />
                    </TD>
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
