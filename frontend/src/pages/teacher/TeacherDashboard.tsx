import { BookOpen, Layers, Plus, Users } from 'lucide-react'
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

export default function TeacherDashboard() {
  const { user } = useAuth()
  const { data, error, loading, reload } = useAsync(dashboardApi.teacher, 'teacher-dashboard')

  return (
    <>
      <PageHeader
        title={`Welcome, ${user?.full_name.split(' ')[0] ?? ''}`}
        description="An overview of your courses and recent activity."
        actions={
          <Link to="/teacher/courses?new=1" className={buttonVariants()}>
            <Plus /> New course
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
            <StatCard label="Courses" value={data.course_count} icon={BookOpen} />
            <StatCard label="Sections" value={data.section_count} icon={Layers} />
            <StatCard label="Enrolled students" value={data.student_count} icon={Users} hint="Counted once across courses" />
          </div>

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
