import { BookOpen, GraduationCap, Layers } from 'lucide-react'
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

export default function StudentDashboard() {
  const { user } = useAuth()
  const { data, error, loading, reload } = useAsync(dashboardApi.student, 'student-dashboard')

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
          <Link to="/student/courses" className={buttonVariants({ variant: 'secondary' })}>
            Join a course
          </Link>
        }
      />

      {loading && !data ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : data ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <StatCard label="Courses" value={data.course_count} icon={BookOpen} />
            <StatCard label="Sections joined" value={data.enrollment_count} icon={Layers} />
          </div>

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
