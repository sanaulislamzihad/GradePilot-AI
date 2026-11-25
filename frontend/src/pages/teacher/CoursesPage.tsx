import { BookOpen, Plus, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pagination } from '@/components/ui/Pagination'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table'
import { useAsync } from '@/hooks/useAsync'
import { useDebounced } from '@/hooks/useDebounced'
import { courseApi } from '@/services/api'
import { formatDate } from '@/utils/format'
import { CourseFormDialog } from './CourseFormDialog'

const PAGE_SIZE = 10

export default function CoursesPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const debouncedQuery = useDebounced(query, 300)
  const [creating, setCreating] = useState(params.get('new') === '1')

  // "?new=1" (from the dashboard) opens the dialog once, then is removed from the URL.
  useEffect(() => {
    if (params.get('new') === '1') setParams({}, { replace: true })
  }, [params, setParams])

  const { data, error, loading, reload } = useAsync(
    () => courseApi.list({ q: debouncedQuery || undefined, page, page_size: PAGE_SIZE }),
    `courses:${debouncedQuery}:${page}`,
  )

  return (
    <>
      <PageHeader
        title="Courses"
        description="Courses and sections organise your students. Exams can be linked to a course and section."
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus /> New course
          </Button>
        }
      />

      <Card>
        <div className="border-b border-zinc-200 p-3">
          <div className="relative max-w-xs">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-zinc-400" aria-hidden />
            <Input
              type="search"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value)
                setPage(1)
              }}
              placeholder="Search by code or name"
              aria-label="Search courses"
              className="pl-9"
            />
          </div>
        </div>

        {loading && !data ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : data && data.items.length === 0 ? (
          debouncedQuery ? (
            <EmptyState icon={Search} title="No matching courses" description={`Nothing matches “${debouncedQuery}”.`} />
          ) : (
            <EmptyState
              icon={BookOpen}
              title="Create your first course"
              description="Add a course, then create sections and share their join codes with students."
              action={
                <Button variant="secondary" size="sm" onClick={() => setCreating(true)}>
                  <Plus /> New course
                </Button>
              }
            />
          )
        ) : data ? (
          <>
            <Table>
              <THead>
                <tr>
                  <TH>Course</TH>
                  <TH className="text-right">Sections</TH>
                  <TH className="text-right">Students</TH>
                  <TH className="hidden md:table-cell">Created</TH>
                </tr>
              </THead>
              <TBody>
                {data.items.map((course) => (
                  <TR key={course.id} className="cursor-pointer" onClick={() => navigate(`/teacher/courses/${course.id}`)}>
                    <TD>
                      <Link to={`/teacher/courses/${course.id}`} className="font-medium text-zinc-900 hover:underline" onClick={(e) => e.stopPropagation()}>
                        {course.name}
                      </Link>
                      <p className="font-mono text-xs text-zinc-500">{course.code}</p>
                    </TD>
                    <TD className="text-right tabular-nums">{course.section_count}</TD>
                    <TD className="text-right tabular-nums">{course.student_count}</TD>
                    <TD className="hidden text-zinc-500 md:table-cell">{formatDate(course.created_at)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />
          </>
        ) : null}
      </Card>

      <CourseFormDialog
        open={creating}
        onOpenChange={setCreating}
        onSubmit={async (payload) => {
          const course = await courseApi.create(payload)
          toast.success(`Course ${course.code} created`)
          navigate(`/teacher/courses/${course.id}`)
        }}
      />
    </>
  )
}
