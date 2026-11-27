import { BookOpen, ClipboardList, GraduationCap, Inbox } from 'lucide-react'
import { Link } from 'react-router'
import { ActivityList } from '@/components/ActivityList'
import { buttonVariants } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatCard } from '@/components/ui/StatCard'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { useAsync } from '@/hooks/useAsync'
import { useAuth } from '@/hooks/useAuth'
import { ResultList } from '@/pages/student/results/MyResultsPage'
import { dashboardApi, resultsApi } from '@/services/api'
import { formatDateTime, formatRelative } from '@/utils/format'

export default function StudentDashboard() {
  const { user } = useAuth()
  const { data, error, loading, reload } = useAsync(dashboardApi.student, 'student-dashboard')
  const results = useAsync(resultsApi.mine, 'student-dashboard-results')

  return (
    <>
      <PageHeader
        title={`Welcome, ${user?.full_name.split(' ')[0] ?? ''}`}
        description={
          <>
            Student ID <span className="font-mono text-zinc-700">{user?.student_id}</span>
          </>
        }
        actions={
          <Link to="/student/exams" className={buttonVariants()}>
            Available exams
          </Link>
        }
      />

      {loading && !data ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : data ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard label="Available exams" value={data.available_exam_count} icon={ClipboardList} />
            <StatCard label="Submitted" value={data.submitted_exam_count} icon={Inbox} />
            <StatCard label="Courses" value={data.course_count} icon={BookOpen} hint={`${data.enrollment_count} section${data.enrollment_count === 1 ? '' : 's'} joined`} />
          </div>

          <Card>
            <CardHeader title="Upcoming deadlines" description="Open exams you have not submitted yet." />
            {data.upcoming_exams.length === 0 ? (
              <p className="px-5 py-6 text-sm text-zinc-500">Nothing due. You are up to date.</p>
            ) : (
              <ul className="divide-y divide-zinc-100">
                {data.upcoming_exams.map((exam) => (
                  <li key={exam.id}>
                    <Link to={`/student/exams/${exam.slug}`} className="flex items-center justify-between gap-4 px-5 py-3.5 hover:bg-zinc-50">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-zinc-900">{exam.title}</p>
                        <p className="text-xs text-zinc-500">
                          {exam.course_code && <span className="font-mono">{exam.course_code} · </span>}
                          Due {formatDateTime(exam.submission_deadline)}
                        </p>
                      </div>
                      {exam.submission_deadline && (
                        <span className="shrink-0 text-xs font-medium text-zinc-700">{formatRelative(exam.submission_deadline)}</span>
                      )}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {results.data && results.data.length > 0 && (
            <Card>
              <CardHeader
                title="Latest results"
                action={
                  <Link to="/student/results" className="text-sm font-medium text-zinc-600 hover:text-zinc-900">
                    View all
                  </Link>
                }
              />
              <ResultList items={results.data.slice(0, 3)} />
            </Card>
          )}

          <div className="grid gap-6 lg:grid-cols-5">
            <Card className="lg:col-span-3">
              <CardHeader title="My courses" />
              {data.enrollments.length === 0 ? (
                <EmptyState
                  icon={GraduationCap}
                  title="You have not joined a course yet"
                  description="Ask your teacher for the section join code, then enter it on the My Courses page."
                  action={
                    <Link to="/student/courses" className={buttonVariants({ variant: 'secondary', size: 'sm' })}>
                      Enter a join code
                    </Link>
                  }
                />
              ) : (
                <ul className="divide-y divide-zinc-100">
                  {data.enrollments.map((e) => (
                    <li key={e.enrollment_id} className="flex items-center justify-between gap-4 px-5 py-3.5">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-zinc-900">{e.course_name}</p>
                        <p className="text-xs text-zinc-500">
                          <span className="font-mono">{e.course_code}</span> · Section {e.section_name}
                        </p>
                      </div>
                      <p className="shrink-0 text-xs text-zinc-500">{e.teacher_name}</p>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader title="Recent activity" />
              <ActivityList items={data.recent_activity} />
            </Card>
          </div>
        </div>
      ) : null}
    </>
  )
}
