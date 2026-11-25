import { UserMinus, Users } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { useAsync } from '@/hooks/useAsync'
import { courseApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import type { EnrolledStudent, Section } from '@/types/api'
import { formatDate } from '@/utils/format'

function Roster({ section, onRemoved }: { section: Section; onRemoved: (sectionId: string) => void }) {
  const { data: students, error, loading, reload, setData } = useAsync(
    () => courseApi.students(section.id),
    `roster:${section.id}`,
  )
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  const [removingId, setRemovingId] = useState<string | null>(null)

  const remove = async (student: EnrolledStudent) => {
    setRemovingId(student.enrollment_id)
    try {
      await courseApi.removeStudent(section.id, student.enrollment_id)
      setData((current) => current?.filter((s) => s.enrollment_id !== student.enrollment_id) ?? null)
      onRemoved(section.id)
      toast.success(`${student.full_name} removed from the section`)
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setRemovingId(null)
      setConfirmingId(null)
    }
  }

  if (error) return <ErrorState message={error} onRetry={reload} />
  if (loading && !students) return <LoadingState />
  if (!students || students.length === 0) {
    return <EmptyState icon={Users} title="No students yet" description="Share the join code so students can enroll." />
  }

  return (
    <ul className="divide-y divide-zinc-100">
      {students.map((student) => (
        <li key={student.enrollment_id} className="flex items-center justify-between gap-3 px-5 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-zinc-900">{student.full_name}</p>
            <p className="truncate text-xs text-zinc-500">
              <span className="font-mono">{student.student_id}</span> · {student.email} · joined {formatDate(student.joined_at)}
            </p>
          </div>
          {confirmingId === student.enrollment_id ? (
            <div className="flex shrink-0 gap-1">
              <Button size="sm" variant="ghost" onClick={() => setConfirmingId(null)} disabled={removingId !== null}>
                Cancel
              </Button>
              <Button size="sm" variant="dangerSolid" loading={removingId === student.enrollment_id} onClick={() => remove(student)}>
                Remove
              </Button>
            </div>
          ) : (
            <Button size="icon" variant="ghost" onClick={() => setConfirmingId(student.enrollment_id)} aria-label={`Remove ${student.full_name}`}>
              <UserMinus />
            </Button>
          )}
        </li>
      ))}
    </ul>
  )
}

interface SectionRosterDialogProps {
  section: Section | null
  courseCode: string
  onClose: () => void
  onRemoved: (sectionId: string) => void
}

export function SectionRosterDialog({ section, courseCode, onClose, onRemoved }: SectionRosterDialogProps) {
  return (
    <Dialog
      open={section !== null}
      onOpenChange={(open) => !open && onClose()}
      title={section ? `${courseCode} · Section ${section.name}` : ''}
      description="Students enrolled in this section."
    >
      <div className="-mx-5 max-h-[60vh] overflow-y-auto border-t border-zinc-200">
        {section && <Roster key={section.id} section={section} onRemoved={onRemoved} />}
      </div>
    </Dialog>
  )
}
