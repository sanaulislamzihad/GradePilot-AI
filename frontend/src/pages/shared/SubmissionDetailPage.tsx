import { ArrowLeft, Award } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { SubmissionFiles } from '@/components/SubmissionFiles'
import { SubmissionStatusBadge } from '@/components/SubmissionStatusBadge'
import { buttonVariants } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { ErrorState, LoadingState } from '@/components/ui/States'
import { useAiSlots } from '@/hooks/useAiSlots'
import { useAsync } from '@/hooks/useAsync'
import { useAuth } from '@/hooks/useAuth'
import { usePolling } from '@/hooks/usePolling'
import { ExtractionEditor } from '@/pages/teacher/submission/ExtractionEditor'
import { ProcessingPanel } from '@/pages/teacher/submission/ProcessingPanel'
import { ReviewPanel } from '@/pages/teacher/submission/ReviewPanel'
import { processingApi, resultsApi, submissionApi } from '@/services/api'
import type { SubmissionDetail } from '@/types/api'
import { formatBytes, formatDateTime } from '@/utils/format'
import { IN_PROGRESS_STATUSES } from '@/utils/submissionStatus'

const MAY_HAVE_RESULT = ['teacher_review_required', 'approved', 'published']

const AFTER_EXTRACTION = ['ocr_review_required', 'ready_for_evaluation', 'evaluating', 'teacher_review_required', 'failed', 'approved', 'published']

function TeacherProcessing({ submission, onUpdated }: { submission: SubmissionDetail; onUpdated: (s: SubmissionDetail) => void }) {
  const slots = useAiSlots()
  const showExtraction = AFTER_EXTRACTION.includes(submission.status)
  const extraction = useAsync(
    () => (showExtraction ? processingApi.extractedAnswers(submission.id) : Promise.resolve(null)),
    `extraction:${submission.id}:${submission.status}`,
  )
  const evaluation = useAsync(
    () => processingApi.evaluation(submission.id).catch(() => null),
    `evaluation:${submission.id}:${submission.status}`,
  )

  return (
    <>
      <ProcessingPanel submission={submission} hasEvaluator={slots.has('evaluator')} onUpdated={onUpdated} />
      {extraction.data && extraction.data.answers.length > 0 && (
        <ExtractionEditor
          key={`${submission.status}:${extraction.data.answers.map((a) => a.source + a.text.length).join()}`}
          submissionId={submission.id}
          view={extraction.data}
          onSaved={async (view, confirmed) => {
            extraction.setData(() => view)
            if (confirmed) onUpdated(await processingApi.evaluate(submission.id))
          }}
        />
      )}
      {evaluation.data && (
        <ReviewPanel
          key={`${evaluation.data.id}:${evaluation.data.review_status}`}
          evaluation={evaluation.data}
          submission={submission}
          onEvaluation={(updated) => evaluation.setData(() => updated)}
          onSubmission={onUpdated}
        />
      )}
    </>
  )
}

/** One submission, for its student or for the teacher who owns the exam. */
export default function SubmissionDetailPage() {
  const { submissionId = '' } = useParams()
  const { user } = useAuth()
  const isTeacher = user?.role === 'teacher'
  const { data: submission, error, loading, reload, setData } = useAsync(
    () => submissionApi.get(submissionId),
    `submission:${submissionId}`,
  )
  usePolling(Boolean(submission && IN_PROGRESS_STATUSES.includes(submission.status)), reload)
  // Students: a result exists once it is published, or earlier if the exam shows provisional marks.
  const checkResult = Boolean(!isTeacher && submission?.is_latest && MAY_HAVE_RESULT.includes(submission.status))
  const result = useAsync(
    () => (checkResult ? resultsApi.get(submissionId).catch(() => null) : Promise.resolve(null)),
    `submission-result:${submissionId}:${checkResult ? submission?.status : ''}`,
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
        actions={
          result.data && (
            <Link to={`/student/results/${submission.id}`} className={buttonVariants()}>
              <Award /> {result.data.provisional ? 'View provisional result' : 'View result'}
            </Link>
          )
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {isTeacher && submission.is_latest && (
            <TeacherProcessing submission={submission} onUpdated={(updated) => setData(() => updated)} />
          )}
          <Card>
            <CardHeader title="Answer script" description="Files are private to the student and the exam's teacher." />
            <SubmissionFiles submission={submission} />
          </Card>
          {!isTeacher && submission.status_message && (
            <Card>
              <CardHeader title="Status" />
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
