import { GraduationCap, LogOut } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { FormAlert } from '@/components/FormAlert'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { PageHeader } from '@/components/ui/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table'
import { useAsync } from '@/hooks/useAsync'
import { studentApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import type { StudentEnrollment } from '@/types/api'
import { formatDate } from '@/utils/format'

export default function StudentCoursesPage() {
  const { data, error, loading, reload, setData } = useAsync(studentApi.enrollments, 'enrollments')
  const [code, setCode] = useState('')
  const [joining, setJoining] = useState(false)
  const [joinError, setJoinError] = useState<string | null>(null)
  const [leaving, setLeaving] = useState<StudentEnrollment | null>(null)

  const join = async (event: FormEvent) => {
    event.preventDefault()
    const trimmed = code.trim()
    if (trimmed.length < 4) {
      setJoinError('Enter the join code your teacher shared')
      return
    }
    setJoining(true)
    setJoinError(null)
    try {
      const enrollment = await studentApi.join(trimmed)
      setData((current) => [enrollment, ...(current ?? [])])
      setCode('')
      toast.success(`Joined ${enrollment.course_code} section ${enrollment.section_name}`)
    } catch (err) {
      setJoinError(errorMessage(err))
    } finally {
      setJoining(false)
    }
  }

  return (
    <>
      <PageHeader title="My Courses" description="Join a course section with the code from your teacher." />

      <div className="space-y-6">
        <Card>
          <CardHeader title="Join a section" />
          <CardBody>
            <form onSubmit={join} noValidate className="space-y-3">
              <FormAlert message={joinError} />
              <div className="flex max-w-md gap-2">
                <Input
                  value={code}
                  onChange={(event) => setCode(event.target.value.toUpperCase())}
                  placeholder="Join code, e.g. K7PM2QXR"
                  aria-label="Join code"
                  maxLength={12}
                  autoComplete="off"
                  className="font-mono tracking-widest uppercase placeholder:font-sans placeholder:tracking-normal placeholder:normal-case"
                />
                <Button type="submit" loading={joining}>
                  Join
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Enrolled sections" />
          {loading && !data ? (
            <LoadingState />
          ) : error ? (
            <ErrorState message={error} onRetry={reload} />
          ) : data && data.length === 0 ? (
            <EmptyState icon={GraduationCap} title="No courses yet" description="Sections you join will appear here." />
          ) : data ? (
            <Table>
              <THead>
                <tr>
                  <TH>Course</TH>
                  <TH>Section</TH>
                  <TH className="hidden sm:table-cell">Teacher</TH>
                  <TH className="hidden md:table-cell">Joined</TH>
                  <TH className="w-12">
                    <span className="sr-only">Actions</span>
                  </TH>
                </tr>
              </THead>
              <TBody>
                {data.map((e) => (
                  <TR key={e.enrollment_id}>
                    <TD>
                      <p className="font-medium text-zinc-900">{e.course_name}</p>
                      <p className="font-mono text-xs text-zinc-500">{e.course_code}</p>
                    </TD>
                    <TD>{e.section_name}</TD>
                    <TD className="hidden sm:table-cell">{e.teacher_name}</TD>
                    <TD className="hidden text-zinc-500 md:table-cell">{formatDate(e.joined_at)}</TD>
                    <TD>
                      <Button variant="ghost" size="icon" onClick={() => setLeaving(e)} aria-label={`Leave ${e.course_code}`}>
                        <LogOut />
                      </Button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          ) : null}
        </Card>
      </div>

      <ConfirmDialog
        open={leaving !== null}
        onOpenChange={(open) => !open && setLeaving(null)}
        title={leaving ? `Leave ${leaving.course_code}?` : ''}
        description="You will need a join code from your teacher to enroll again."
        confirmLabel="Leave section"
        destructive
        onConfirm={async () => {
          if (!leaving) return
          await studentApi.leave(leaving.enrollment_id)
          setData((current) => current?.filter((e) => e.enrollment_id !== leaving.enrollment_id) ?? null)
          toast.success(`Left ${leaving.course_code}`)
        }}
      />
    </>
  )
}
