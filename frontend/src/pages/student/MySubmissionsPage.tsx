import { Inbox } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { SubmissionStatusBadge } from '@/components/SubmissionStatusBadge'
import { buttonVariants } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pagination } from '@/components/ui/Pagination'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table'
import { useAsync } from '@/hooks/useAsync'
import { submissionApi } from '@/services/api'
import { formatDateTime } from '@/utils/format'

const PAGE_SIZE = 20

export default function MySubmissionsPage() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const { data, error, loading, reload } = useAsync(
    () => submissionApi.list({ latest_only: false, page, page_size: PAGE_SIZE }),
    `my-submissions:${page}`,
  )

  return (
    <>
      <PageHeader title="My Submissions" description="Every script you have submitted, including replaced attempts." />
      <Card>
        {loading && !data ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : data && data.items.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="No submissions yet"
            description="Open an exam to upload your answer script."
            action={
              <Link to="/student/exams" className={buttonVariants({ variant: 'secondary', size: 'sm' })}>
                Available exams
              </Link>
            }
          />
        ) : data ? (
          <>
            <Table>
              <THead>
                <tr>
                  <TH>Submission ID</TH>
                  <TH>Exam</TH>
                  <TH className="hidden sm:table-cell">Attempt</TH>
                  <TH className="hidden md:table-cell">Submitted</TH>
                  <TH>Status</TH>
                </tr>
              </THead>
              <TBody>
                {data.items.map((s) => (
                  <TR key={s.id} className="cursor-pointer" onClick={() => navigate(`/student/submissions/${s.id}`)}>
                    <TD>
                      <Link to={`/student/submissions/${s.id}`} onClick={(e) => e.stopPropagation()} className="font-mono font-medium text-zinc-900 hover:underline">
                        {s.code}
                      </Link>
                      {!s.is_latest && <p className="text-xs text-zinc-400">Replaced</p>}
                    </TD>
                    <TD>
                      <p className="text-zinc-900">{s.exam_title}</p>
                      {s.course_code && <p className="font-mono text-xs text-zinc-500">{s.course_code}</p>}
                    </TD>
                    <TD className="hidden tabular-nums sm:table-cell">{s.attempt_number}</TD>
                    <TD className="hidden text-zinc-500 md:table-cell">{formatDateTime(s.submitted_at)}</TD>
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
