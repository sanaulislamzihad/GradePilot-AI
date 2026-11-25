import { CalendarClock, FileUp, Repeat, User } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { Logo } from '@/components/Logo'
import { StatusBadge } from '@/components/ui/Badge'
import { buttonVariants } from '@/components/ui/Button'
import { Card, CardBody } from '@/components/ui/Card'
import { ErrorState, LoadingState } from '@/components/ui/States'
import { useAsync } from '@/hooks/useAsync'
import { useAuth } from '@/hooks/useAuth'
import { homePath } from '@/layouts/navigation'
import { publicApi } from '@/services/api'
import { examTypeLabel, formatDate, formatDateTime, formatMarks } from '@/utils/format'

export default function PublicExamPage() {
  const { slug = '' } = useParams()
  const { user } = useAuth()
  const { data: exam, error, loading, reload } = useAsync(() => publicApi.exam(slug), `public-exam:${slug}`)

  const formats = exam ? [...new Set(exam.allowed_formats.map((f) => (f === 'jpeg' ? 'jpg' : f)))].map((f) => f.toUpperCase()) : []

  return (
    <div className="min-h-screen bg-zinc-50/60">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
          <Link to="/">
            <Logo />
          </Link>
          {user ? (
            <Link to={homePath[user.role]} className="text-sm font-medium text-zinc-700 hover:text-zinc-900">
              Dashboard
            </Link>
          ) : (
            <Link to="/login" state={{ from: `/exam/${slug}` }} className="text-sm font-medium text-zinc-700 hover:text-zinc-900">
              Sign in
            </Link>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-10">
        {loading && !exam ? (
          <LoadingState />
        ) : error || !exam ? (
          <ErrorState message={error ?? 'Exam not found'} onRetry={reload} />
        ) : (
          <div className="space-y-6">
            <div>
              <div className="flex flex-wrap items-center gap-2 text-sm text-zinc-500">
                <span>{examTypeLabel[exam.exam_type]}</span>
                {exam.course_code && (
                  <>
                    <span aria-hidden>·</span>
                    <span className="font-mono">{exam.course_code}</span>
                    {exam.course_name && <span>{exam.course_name}</span>}
                    {exam.section_name && <span>· Section {exam.section_name}</span>}
                  </>
                )}
              </div>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-900 sm:text-3xl">{exam.title}</h1>
              <div className="mt-3">
                <StatusBadge tone={exam.is_open ? 'positive' : 'muted'}>{exam.is_open ? 'Open for submission' : 'Closed'}</StatusBadge>
              </div>
            </div>

            <Card>
              <dl className="grid divide-y divide-zinc-100 sm:grid-cols-2 sm:divide-y-0">
                {[
                  [User, 'Teacher', exam.teacher_name],
                  [CalendarClock, 'Submission deadline', formatDateTime(exam.submission_deadline)],
                  [FileUp, 'Accepted files', `${formats.join(', ')} · up to ${exam.max_file_size_mb} MB`],
                  [Repeat, 'Attempts allowed', String(exam.max_attempts)],
                ].map(([Icon, label, value]) => {
                  const I = Icon as typeof User
                  return (
                    <div key={label as string} className="flex gap-3 px-5 py-4 sm:border-b sm:border-zinc-100">
                      <I className="mt-0.5 size-4 shrink-0 text-zinc-400" aria-hidden />
                      <div>
                        <dt className="text-xs text-zinc-500">{label as string}</dt>
                        <dd className="mt-0.5 text-sm text-zinc-900">{value as string}</dd>
                      </div>
                    </div>
                  )
                })}
              </dl>
              <div className="flex flex-wrap gap-x-6 gap-y-1 px-5 py-3 text-sm text-zinc-600">
                <span>
                  Total marks <strong className="font-semibold text-zinc-900">{formatMarks(exam.total_marks)}</strong>
                </span>
                <span>
                  Questions <strong className="font-semibold text-zinc-900">{exam.question_count}</strong>
                </span>
                {exam.exam_date && <span>Exam date {formatDate(exam.exam_date)}</span>}
              </div>
            </Card>

            {exam.instructions && (
              <Card>
                <CardBody>
                  <h2 className="text-sm font-semibold text-zinc-900">Instructions</h2>
                  <p className="mt-2 text-sm leading-relaxed whitespace-pre-line text-zinc-700">{exam.instructions}</p>
                </CardBody>
              </Card>
            )}

            <Card>
              <CardBody className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-zinc-700">
                  {user?.role === 'student'
                    ? 'Upload your answer script from your student account.'
                    : user
                      ? 'Students submit their answer scripts after signing in with a student account.'
                      : 'Sign in with your student account to submit your answer script.'}
                </p>
                {(!user || user.role === 'student') && (
                  <Link to={`/student/exams/${slug}`} className={buttonVariants({ className: 'shrink-0' })}>
                    {user ? 'Open submission page' : 'Sign in to submit'}
                  </Link>
                )}
              </CardBody>
            </Card>
          </div>
        )}
      </main>
    </div>
  )
}
