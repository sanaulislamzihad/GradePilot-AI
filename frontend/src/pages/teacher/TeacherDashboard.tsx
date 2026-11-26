import { BookOpen, FileText, Inbox, Plus, Users } from 'lucide-react'
import { Link } from 'react-router'
import { ActivityList } from '@/components/ActivityList'
import { buttonVariants } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatCard } from '@/components/ui/StatCard'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { useAsync } from '@/hooks/useAsync'
import { useAuth } from '@/hooks/useAuth'
import { dashboardApi } from '@/services/api'
import { formatDateTime } from '@/utils/format'
import { ExamStatusBadge } from './exams/ExamStatusBadge'

export default function TeacherDashboard() {
  const { user } = useAuth()
  const { data, error, loading, reload } = useAsync(dashboardApi.teacher, 'teacher-dashboard')

  return (
    <>
      <PageHeader
        title={`Welcome, ${user?.full_name.split(' ')[0] ?? ''}`}
        description="An overview of your courses and recent activity."
        actions={
          <Link to="/teacher/exams/new" className={buttonVariants()}>
            <Plus /> Create exam
          </Link>
        }
      />

      {loading && !data ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : data ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Exams"
              value={data.exam_count}
              icon={FileText}
              hint={`${data.published_exam_count} published · ${data.draft_exam_count} draft`}
            />
            <StatCard label="Submissions" value={data.submission_count} icon={Inbox} hint="Current script per student" />
            <StatCard label="Courses" value={data.course_count} icon={BookOpen} hint={`${data.section_count} sections`} />
            <StatCard label="Enrolled students" value={data.student_count} icon={Users} hint="Counted once across courses" />
          </div>

          <Card>
            <CardHeader
              title="Recent exams"
              action={
                data.exam_count > 0 && (
                  <Link to="/teacher/exams" className="text-sm font-medium text-zinc-600 hover:text-zinc-900">
                    View all
                  </Link>
                )
              }
            />
            {data.recent_exams.length === 0 ? (
              <EmptyState
                icon={FileText}
                title="No exams yet"
                description="Create an exam, add the question paper, marks, model answers and rubrics, then publish it."
                action={
                  <Link to="/teacher/exams/new" className={buttonVariants({ variant: 'secondary', size: 'sm' })}>
                    <Plus /> Create exam
                  </Link>
                }
              />
            ) : (
              <ul className="divide-y divide-zinc-100">
                {data.recent_exams.map((exam) => (
                  <li key={exam.id}>
                    <Link to={`/teacher/exams/${exam.id}`} className="flex items-center justify-between gap-4 px-5 py-3.5 hover:bg-zinc-50">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-zinc-900">{exam.title}</p>
                        <p className="text-xs text-zinc-500">
                          {exam.course_code && <span className="font-mono">{exam.course_code} · </span>}
                          Deadline {formatDateTime(exam.submission_deadline)}
                        </p>
                      </div>
                      <ExamStatusBadge status={exam.status} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <div className="grid gap-6 lg:grid-cols-5">
            <Card className="lg:col-span-3">
              <CardHeader
                title="Your courses"
                action={
                  data.course_count > 0 && (
                    <Link to="/teacher/courses" className="text-sm font-medium text-zinc-600 hover:text-zinc-900">
                      View all
                    </Link>
                  )
                }
              />
              {data.courses.length === 0 ? (
                <EmptyState
                  icon={BookOpen}
                  title="No courses yet"
                  description="Create a course, add sections and share the join codes with your students."
                  action={
                    <Link to="/teacher/courses?new=1" className={buttonVariants({ variant: 'secondary', size: 'sm' })}>
                      <Plus /> Create course
                    </Link>
                  }
                />
              ) : (
                <ul className="divide-y divide-zinc-100">
                  {data.courses.map((course) => (
                    <li key={course.id}>
                      <Link
                        to={`/teacher/courses/${course.id}`}
                        className="flex items-center justify-between gap-4 px-5 py-3.5 hover:bg-zinc-50"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-zinc-900">{course.name}</p>
                          <p className="font-mono text-xs text-zinc-500">{course.code}</p>
                        </div>
                        <p className="shrink-0 text-xs text-zinc-500 tabular-nums">
                          {course.section_count} {course.section_count === 1 ? 'section' : 'sections'} ·{' '}
                          {course.student_count} {course.student_count === 1 ? 'student' : 'students'}
                        </p>
                      </Link>
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
