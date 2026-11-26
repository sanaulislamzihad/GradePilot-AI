import { ArrowLeft, CheckCircle2, Info } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { toast } from 'sonner'
import { FormAlert } from '@/components/FormAlert'
import { ScriptPicker } from '@/components/ScriptPicker'
import { SubmissionStatusBadge } from '@/components/SubmissionStatusBadge'
import { StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/Dialog'
import { PageHeader } from '@/components/ui/PageHeader'
import { ErrorState, LoadingState } from '@/components/ui/States'
import { TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table'
import { useAsync } from '@/hooks/useAsync'
import { useAuth } from '@/hooks/useAuth'
import { studentApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import type { StudentExamDetail, SubmissionDetail } from '@/types/api'
import { examTypeLabel, formatBytes, formatDate, formatDateTime, formatMarks, formatRelative } from '@/utils/format'

function newKey() {
  return crypto.randomUUID()
}

function Receipt({ submission }: { submission: SubmissionDetail }) {
  return (
    <div role="status" className="rounded-lg border border-zinc-900 bg-white p-5">
      <div className="flex items-start gap-3">
        <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-zinc-900" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-zinc-900">Your script was submitted</p>
          <p className="mt-0.5 text-sm text-zinc-600">Keep the submission ID for your records.</p>
          <dl className="mt-4 grid gap-3 sm:grid-cols-3">
            <div>
              <dt className="text-xs text-zinc-500">Submission ID</dt>
              <dd className="mt-0.5 font-mono text-lg font-semibold tracking-wide text-zinc-900 select-all">{submission.code}</dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">Submitted</dt>
              <dd className="mt-0.5 text-sm text-zinc-900">{formatDateTime(submission.submitted_at)}</dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">Status</dt>
              <dd className="mt-1">
                <SubmissionStatusBadge status={submission.status} />
              </dd>
            </div>
          </dl>
          <p className="mt-3 text-[13px] text-zinc-500">
            {submission.file_count} file{submission.file_count === 1 ? '' : 's'} · {submission.page_count} page
            {submission.page_count === 1 ? '' : 's'} · {formatBytes(submission.total_size_bytes)} · attempt {submission.attempt_number} of{' '}
            {submission.max_attempts}
          </p>
        </div>
      </div>
    </div>
  )
}

function SubmitForm({ exam, onSubmitted }: { exam: StudentExamDetail; onSubmitted: (s: SubmissionDetail) => void }) {
  const { user } = useAuth()
  const [files, setFiles] = useState<File[]>([])
  // One key per intended submission: retrying the same upload cannot create a second attempt.
  const [idempotencyKey, setIdempotencyKey] = useState(newKey)
  const [confirming, setConfirming] = useState(false)
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const replacing = exam.attempts_used > 0

  const changeFiles = (next: File[]) => {
    setFiles(next)
    setIdempotencyKey(newKey())
    setError(null)
  }

  const send = async () => {
    setError(null)
    setProgress(0)
    try {
      const submission = await studentApi.submit(exam.id, files, idempotencyKey, setProgress)
      setFiles([])
      setIdempotencyKey(newKey())
      onSubmitted(submission)
    } catch (err) {
      setError(errorMessage(err))
      throw err
    } finally {
      setProgress(null)
    }
  }

  return (
    <Card>
      <CardHeader
        title={replacing ? 'Submit a replacement' : 'Submit your answer script'}
        description={
          replacing
            ? `A new attempt replaces your current submission. ${exam.attempts_left} attempt${exam.attempts_left === 1 ? '' : 's'} left.`
            : `You can submit ${exam.max_attempts === 1 ? 'once' : `up to ${exam.max_attempts} times`}. Check your files before submitting.`
        }
      />
      <CardBody className="space-y-4">
        <dl className="grid gap-3 rounded-md bg-zinc-50 px-4 py-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs text-zinc-500">Name</dt>
            <dd className="text-zinc-900">{user?.full_name}</dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">Student ID</dt>
            <dd className="font-mono text-zinc-900">{user?.student_id}</dd>
          </div>
        </dl>
        <FormAlert message={error} />
        <ScriptPicker
          files={files}
          onChange={changeFiles}
          formats={exam.allowed_formats}
          maxFileBytes={exam.max_file_size_mb * 1024 * 1024}
          disabled={progress !== null}
        />
        {progress !== null && (
          <div className="space-y-1" role="progressbar" aria-valuenow={Math.round(progress * 100)} aria-valuemin={0} aria-valuemax={100} aria-label="Upload progress">
            <div className="h-1.5 overflow-hidden rounded-full bg-zinc-100">
              <div className="h-full bg-zinc-900 transition-all" style={{ width: `${Math.round(progress * 100)}%` }} />
            </div>
            <p className="text-xs text-zinc-500">{progress < 1 ? `Uploading… ${Math.round(progress * 100)}%` : 'Checking your files…'}</p>
          </div>
        )}
        <div className="flex justify-end">
          <Button onClick={() => setConfirming(true)} disabled={!files.length || progress !== null}>
            {replacing ? 'Submit replacement' : 'Submit script'}
          </Button>
        </div>
      </CardBody>

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={replacing ? 'Replace your current submission?' : 'Submit your answer script?'}
        description={`Attempt ${exam.attempts_used + 1} of ${exam.max_attempts}: ${files.length} file${files.length === 1 ? '' : 's'}, ${formatBytes(files.reduce((s, f) => s + f.size, 0))}. ${
          exam.attempts_left === 1 ? 'This is your last attempt; it cannot be changed afterwards.' : ''
        }`}
        confirmLabel="Submit"
        onConfirm={send}
      />
    </Card>
  )
}

export default function StudentExamPage() {
  const { slug = '' } = useParams()
  const { data: exam, error, loading, reload } = useAsync(() => studentApi.exam(slug), `student-exam:${slug}`)
  const [receipt, setReceipt] = useState<SubmissionDetail | null>(null)

  if (loading && !exam) return <LoadingState />
  if (error || !exam) return <ErrorState message={error ?? 'Exam not found'} onRetry={reload} />

  const formats = [...new Set(exam.allowed_formats.map((f) => (f === 'jpeg' ? 'jpg' : f)))].map((f) => f.toUpperCase())

  return (
    <>
      <PageHeader
        eyebrow={
          <Link to="/student/exams" className="inline-flex items-center gap-1 hover:text-zinc-900">
            <ArrowLeft className="size-3.5" /> Available Exams
          </Link>
        }
        title={exam.title}
        description={
          <span className="inline-flex flex-wrap items-center gap-x-2">
            <span>{examTypeLabel[exam.exam_type]}</span>
            {exam.course_code && (
              <>
                <span aria-hidden>·</span>
                <span className="font-mono">{exam.course_code}</span>
                {exam.section_name && <span>Section {exam.section_name}</span>}
              </>
            )}
            <span aria-hidden>·</span>
            <span>{exam.teacher_name}</span>
          </span>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {receipt && <Receipt submission={receipt} />}

          {exam.can_submit ? (
            <SubmitForm
              key={exam.attempts_used}
              exam={exam}
              onSubmitted={(submission) => {
                setReceipt(submission)
                toast.success(`Submitted. Your submission ID is ${submission.code}`)
                reload()
              }}
            />
          ) : (
            !receipt && (
              <div className="flex gap-3 rounded-lg border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-700">
                <Info className="mt-0.5 size-4 shrink-0 text-zinc-500" aria-hidden />
                {exam.blocked_reason}
              </div>
            )
          )}

          {exam.instructions && (
            <Card>
              <CardHeader title="Instructions" />
              <CardBody>
                <p className="text-sm leading-relaxed whitespace-pre-line text-zinc-700">{exam.instructions}</p>
              </CardBody>
            </Card>
          )}

          {exam.submissions.length > 0 && (
            <Card>
              <CardHeader title="Your submissions" />
              <Table>
                <THead>
                  <tr>
                    <TH>Submission ID</TH>
                    <TH>Attempt</TH>
                    <TH className="hidden sm:table-cell">Submitted</TH>
                    <TH>Status</TH>
                  </tr>
                </THead>
                <TBody>
                  {exam.submissions.map((s) => (
                    <TR key={s.id}>
                      <TD>
                        <Link to={`/student/submissions/${s.id}`} className="font-mono font-medium text-zinc-900 hover:underline">
                          {s.code}
                        </Link>
                        {!s.is_latest && <p className="text-xs text-zinc-400">Replaced</p>}
                      </TD>
                      <TD className="tabular-nums">
                        {s.attempt_number} of {exam.max_attempts}
                      </TD>
                      <TD className="hidden text-zinc-500 sm:table-cell">{formatDateTime(s.submitted_at)}</TD>
                      <TD>
                        <SubmissionStatusBadge status={s.status} />
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </Card>
          )}
        </div>

        <Card className="h-fit">
          <CardHeader title="Exam details" action={<StatusBadge tone={exam.is_open ? 'positive' : 'muted'}>{exam.is_open ? 'Open' : 'Closed'}</StatusBadge>} />
          <dl className="divide-y divide-zinc-100 text-sm">
            {[
              ['Deadline', formatDateTime(exam.submission_deadline), exam.is_open && exam.submission_deadline ? `closes ${formatRelative(exam.submission_deadline)}` : null],
              ['Total marks', formatMarks(exam.total_marks), `${exam.question_count} question${exam.question_count === 1 ? '' : 's'}`],
              ['Attempts', `${exam.attempts_used} of ${exam.max_attempts} used`, null],
              ['Accepted files', formats.join(', '), `up to ${exam.max_file_size_mb} MB each`],
              ...(exam.exam_date ? [['Exam date', formatDate(exam.exam_date), null] as const] : []),
            ].map(([label, value, hint]) => (
              <div key={label} className="px-5 py-3">
                <dt className="text-xs text-zinc-500">{label}</dt>
                <dd className="mt-0.5 text-zinc-900">{value}</dd>
                {hint && <dd className="text-xs text-zinc-500">{hint}</dd>}
              </div>
            ))}
          </dl>
        </Card>
      </div>
    </>
  )
}
