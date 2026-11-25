import { BookOpen, Layers, UserCheck, UserPlus, Users } from 'lucide-react'
import { Link } from 'react-router'
import { Card, CardHeader } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatCard } from '@/components/ui/StatCard'
import { ErrorState, LoadingState } from '@/components/ui/States'
import { useAsync } from '@/hooks/useAsync'
import { adminApi } from '@/services/api'
import type { UserRole } from '@/types/api'
import { roleLabel } from '@/utils/format'

const roleOrder: UserRole[] = ['teacher', 'student', 'admin']

export default function AdminDashboard() {
  const { data, error, loading, reload } = useAsync(adminApi.overview, 'admin-overview')

  return (
    <>
      <PageHeader title="Overview" description="Platform-wide accounts and course activity." />
      {loading && !data ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : data ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total users" value={data.total_users} icon={Users} />
            <StatCard label="Active users" value={data.active_users} icon={UserCheck} hint={`${data.total_users - data.active_users} deactivated`} />
            <StatCard label="New in last 7 days" value={data.new_users_last_7_days} icon={UserPlus} />
            <StatCard label="Courses" value={data.course_count} icon={BookOpen} hint={`${data.section_count} sections`} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader title="Users by role" />
              <ul className="divide-y divide-zinc-100">
                {roleOrder.map((role) => {
                  const count = data.users_by_role[role] ?? 0
                  const share = data.total_users ? Math.round((count / data.total_users) * 100) : 0
                  return (
                    <li key={role} className="px-5 py-3.5">
                      <div className="flex items-center justify-between text-sm">
                        <Link to={`/admin/users?role=${role}`} className="font-medium text-zinc-900 hover:underline">
                          {roleLabel[role]}s
                        </Link>
                        <span className="text-zinc-600 tabular-nums">
                          {count} <span className="text-zinc-400">· {share}%</span>
                        </span>
                      </div>
                      <div className="mt-2 h-1.5 rounded-full bg-zinc-100" aria-hidden>
                        <div className="h-1.5 rounded-full bg-zinc-900" style={{ width: `${share}%` }} />
                      </div>
                    </li>
                  )
                })}
              </ul>
            </Card>

            <Card>
              <CardHeader title="Enrollment" />
              <dl className="grid grid-cols-2 divide-x divide-zinc-100">
                <div className="px-5 py-6">
                  <dt className="flex items-center gap-2 text-[13px] text-zinc-500">
                    <Layers className="size-4" aria-hidden /> Sections
                  </dt>
                  <dd className="mt-2 text-2xl font-semibold text-zinc-900 tabular-nums">{data.section_count}</dd>
                </div>
                <div className="px-5 py-6">
                  <dt className="flex items-center gap-2 text-[13px] text-zinc-500">
                    <Users className="size-4" aria-hidden /> Enrollments
                  </dt>
                  <dd className="mt-2 text-2xl font-semibold text-zinc-900 tabular-nums">{data.enrollment_count}</dd>
                </div>
              </dl>
            </Card>
          </div>
        </div>
      ) : null}
    </>
  )
}
