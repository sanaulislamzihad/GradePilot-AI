import { FileText, Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { buttonVariants } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Input, Select } from '@/components/ui/Input'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pagination } from '@/components/ui/Pagination'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table'
import { useAsync } from '@/hooks/useAsync'
import { useDebounced } from '@/hooks/useDebounced'
import { examApi } from '@/services/api'
import type { ExamStatus } from '@/types/api'
import { examTypeLabel, formatDateTime, formatMarks } from '@/utils/format'
import { ExamStatusBadge } from './ExamStatusBadge'

const PAGE_SIZE = 15

export default function ExamsPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<ExamStatus | ''>('')
  const [page, setPage] = useState(1)
  const debouncedQuery = useDebounced(query, 300)

  const { data, error, loading, reload } = useAsync(
    () => examApi.list({ q: debouncedQuery || undefined, status: status || undefined, page, page_size: PAGE_SIZE }),
    `exams:${debouncedQuery}:${status}:${page}`,
  )
  const filtered = Boolean(debouncedQuery || status)

  return (
    <>
      <PageHeader
        title="My Exams"
        description="Drafts stay private. Publishing locks the exam and creates its shareable link."
        actions={
          <Link to="/teacher/exams/new" className={buttonVariants()}>
            <Plus /> Create exam
          </Link>
        }
      />
      <Card>
        <div className="flex flex-col gap-2 border-b border-zinc-200 p-3 sm:flex-row">
          <div className="relative flex-1 sm:max-w-xs">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-zinc-400" aria-hidden />
            <Input
              type="search"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setPage(1)
              }}
              placeholder="Search by title"
              aria-label="Search exams"
              className="pl-9"
            />
          </div>
          <Select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as ExamStatus | '')
              setPage(1)
            }}
            aria-label="Filter by status"
            className="sm:w-40"
          >
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="published">Published</option>
          </Select>
        </div>

        {loading && !data ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : data && data.items.length === 0 ? (
          filtered ? (
            <EmptyState icon={Search} title="No matching exams" description="Try a different search or status." />
          ) : (
            <EmptyState
              icon={FileText}
              title="No exams yet"
              description="Create an exam, add the question paper and rubric, then publish it to students."
              action={
                <Link to="/teacher/exams/new" className={buttonVariants({ variant: 'secondary', size: 'sm' })}>
                  <Plus /> Create exam
                </Link>
              }
            />
          )
        ) : data ? (
          <>
            <Table>
              <THead>
                <tr>
                  <TH>Exam</TH>
                  <TH className="hidden sm:table-cell">Type</TH>
                  <TH className="text-right">Questions</TH>
                  <TH className="text-right">Marks</TH>
                  <TH className="hidden text-right md:table-cell">Submissions</TH>
                  <TH>Status</TH>
                  <TH className="hidden lg:table-cell">Deadline</TH>
                </tr>
              </THead>
              <TBody>
                {data.items.map((exam) => (
                  <TR key={exam.id} className="cursor-pointer" onClick={() => navigate(`/teacher/exams/${exam.id}`)}>
                    <TD>
                      <Link to={`/teacher/exams/${exam.id}`} onClick={(e) => e.stopPropagation()} className="font-medium text-zinc-900 hover:underline">
                        {exam.title}
                      </Link>
                      <p className="text-xs text-zinc-500">
                        {exam.course_code ? (
                          <>
                            <span className="font-mono">{exam.course_code}</span>
                            {exam.section_name && ` · Section ${exam.section_name}`}
                          </>
                        ) : (
                          'No course'
                        )}
                      </p>
                    </TD>
                    <TD className="hidden sm:table-cell">{examTypeLabel[exam.exam_type]}</TD>
                    <TD className="text-right tabular-nums">{exam.question_count}</TD>
                    <TD className="text-right tabular-nums">{formatMarks(exam.total_marks)}</TD>
                    <TD className="hidden text-right tabular-nums md:table-cell">{exam.status === 'published' ? exam.submission_count : '—'}</TD>
                    <TD>
                      <ExamStatusBadge status={exam.status} />
                    </TD>
                    <TD className="hidden text-zinc-500 lg:table-cell">{formatDateTime(exam.submission_deadline)}</TD>
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
