import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { SubmissionFiles } from '@/components/SubmissionFiles'
import { SubmissionStatusBadge } from '@/components/SubmissionStatusBadge'
import { Card, CardHeader } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { ErrorState, LoadingState } from '@/components/ui/States'
import { useAsync } from '@/hooks/useAsync'
import { useAuth } from '@/hooks/useAuth'
import { submissionApi } from '@/services/api'
import { formatBytes, formatDateTime } from '@/utils/format'

/** One submission, for its student or for the teacher who owns the exam. */
export default function SubmissionDetailPage() {
  const { submissionId = '' } = useParams()
  const { user } = useAuth()
  const isTeacher = user?.role === 'teacher'
  const { data: submission, error, loading, reload } = useAsync(
    () => submissionApi.get(submissionId),
    `submission:${submissionId}`,
  )

  if (loading && (!submission || submission.id !== submissionId)) return <LoadingState />
  if (error || !submission) return <ErrorState message={error ?? 'Submission not found'} onRetry={reload} />

  const back = isTeacher
    ? { to: `/teacher/submissions?exam=${submission.exam_id}`, label: 'Submissions' }
    : { to: '/student/submissions', label: 'My Submissions' }

  const facts: [string, string][] = [
    ['Exam', submission.exam_title],
    ['Course', submission.course_code ? `${submission.course_code}${submission.section_name ? ` · Section ${submission.section_name}` : ''}` : '—'],
    ['Student', `${submission.student.full_name} (${submission.student.student_number})`],
    ...(isTeacher ? ([['Email', submission.student.email]] as [string, string][]) : []),
    ['Submitted', formatDateTime(submission.submitted_at)],
    ['Attempt', `${submission.attempt_number} of ${submission.max_attempts}${submission.is_latest ? ' (current)' : ' (replaced by a later attempt)'}`],
    ['Script', `${submission.file_count} file${submission.file_count === 1 ? '' : 's'}, ${submission.page_count} page${submission.page_count === 1 ? '' : 's'}, ${formatBytes(submission.total_size_bytes)}`],
  ]

  return (
    <>
      <PageHeader
        eyebrow={
          <Link to={back.to} className="inline-flex items-center gap-1 hover:text-zinc-900">
            <ArrowLeft className="size-3.5" /> {back.label}
          </Link>
        }
        title={submission.code}
        description={
          <span className="inline-flex items-center gap-2">
            <SubmissionStatusBadge status={submission.status} />
            <span>{submission.exam_title}</span>
          </span>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader title="Answer script" description="Files are private to the student and the exam's teacher." />
            <SubmissionFiles submission={submission} />
          </Card>
          {submission.status_message && (
            <Card>
              <CardHeader title="Processing" />
              <p className="px-5 py-4 text-sm text-zinc-700">{submission.status_message}</p>
            </Card>
          )}
        </div>
        <Card className="h-fit">
          <CardHeader title="Details" />
          <dl className="divide-y divide-zinc-100">
            {facts.map(([label, value]) => (
              <div key={label} className="px-5 py-3">
                <dt className="text-xs text-zinc-500">{label}</dt>
                <dd className="mt-0.5 text-sm break-words text-zinc-900">{value}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>
    </>
  )
}
