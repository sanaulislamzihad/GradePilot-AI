import { ClipboardList } from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import { SubmissionStatusBadge } from '@/components/SubmissionStatusBadge'
import { StatusBadge } from '@/components/ui/Badge'
import { buttonVariants } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table'
import { useAsync } from '@/hooks/useAsync'
import { studentApi } from '@/services/api'
import type { StudentExamItem } from '@/types/api'
import { examTypeLabel, formatDateTime, formatMarks, formatRelative } from '@/utils/format'

export function ExamAvailability({ exam }: { exam: StudentExamItem }) {
  if (exam.latest_submission) return <SubmissionStatusBadge status={exam.latest_submission.status} />
  if (!exam.is_open) return <StatusBadge tone="negative">Missed</StatusBadge>
  return <StatusBadge tone="warning">Not submitted</StatusBadge>
}

export default function AvailableExamsPage() {
  const navigate = useNavigate()
  const { data, error, loading, reload } = useAsync(studentApi.exams, 'student-exams')

  return (
    <>
      <PageHeader
        title="Available Exams"
        description="Published exams for the course sections you have joined. Exams shared by link appear here after you submit."
      />
      <Card>
        {loading && !data ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : data && data.length === 0 ? (
          <EmptyState
            icon={ClipboardList}
            title="No exams available"
            description="Join your course section with the code from your teacher, or open the exam link they shared."
            action={
              <Link to="/student/courses" className={buttonVariants({ variant: 'secondary', size: 'sm' })}>
                Join a section
              </Link>
            }
          />
        ) : data ? (
          <Table>
            <THead>
              <tr>
                <TH>Exam</TH>
                <TH className="hidden md:table-cell">Teacher</TH>
                <TH className="text-right">Marks</TH>
                <TH>Deadline</TH>
                <TH>Status</TH>
              </tr>
            </THead>
            <TBody>
              {data.map((exam) => (
                <TR key={exam.id} className="cursor-pointer" onClick={() => navigate(`/student/exams/${exam.slug}`)}>
                  <TD>
                    <Link to={`/student/exams/${exam.slug}`} onClick={(e) => e.stopPropagation()} className="font-medium text-zinc-900 hover:underline">
                      {exam.title}
                    </Link>
                    <p className="text-xs text-zinc-500">
                      {examTypeLabel[exam.exam_type]}
                      {exam.course_code && (
                        <>
                          {' · '}
                          <span className="font-mono">{exam.course_code}</span>
                          {exam.section_name && ` Section ${exam.section_name}`}
                        </>
                      )}
                    </p>
                  </TD>
                  <TD className="hidden md:table-cell">{exam.teacher_name}</TD>
                  <TD className="text-right tabular-nums">{formatMarks(exam.total_marks)}</TD>
                  <TD>
                    <p className="whitespace-nowrap text-zinc-700">{formatDateTime(exam.submission_deadline)}</p>
                    {exam.is_open && exam.submission_deadline && (
                      <p className="text-xs text-zinc-500">closes {formatRelative(exam.submission_deadline)}</p>
                    )}
                  </TD>
                  <TD>
                    <ExamAvailability exam={exam} />
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        ) : null}
      </Card>
    </>
  )
}
