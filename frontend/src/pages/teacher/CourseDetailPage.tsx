import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { ArrowLeft, Check, Copy, Layers, MoreHorizontal, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'
import { StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { PageHeader } from '@/components/ui/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table'
import { useAsync } from '@/hooks/useAsync'
import { courseApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import type { CourseDetail, Section } from '@/types/api'
import { formatDate } from '@/utils/format'
import { CourseFormDialog } from './CourseFormDialog'
import { SectionRosterDialog } from './SectionRosterDialog'

function CopyCode({ code }: { code: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error('Could not copy. Select the code and copy it manually.')
    }
  }
  return (
    <span className="inline-flex items-center gap-1.5">
      <code className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[13px] tracking-wider text-zinc-900 select-all">{code}</code>
      <button onClick={copy} className="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700" aria-label={`Copy join code ${code}`}>
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      </button>
    </span>
  )
}

const menuItem =
  'flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm text-zinc-700 outline-none data-highlighted:bg-zinc-100'

type PendingAction = { kind: 'delete-section' | 'regenerate'; section: Section } | { kind: 'delete-course' } | null

export default function CourseDetailPage() {
  const { courseId = '' } = useParams()
  const navigate = useNavigate()
  const { data: course, error, loading, reload, setData } = useAsync(() => courseApi.get(courseId), `course:${courseId}`)
  const [editing, setEditing] = useState(false)
  const [pending, setPending] = useState<PendingAction>(null)
  const [rosterSection, setRosterSection] = useState<Section | null>(null)
  const [sectionName, setSectionName] = useState('')
  const [addingSection, setAddingSection] = useState(false)

  const replaceSection = (updated: Section) =>
    setData((current) =>
      current ? { ...current, sections: current.sections.map((s) => (s.id === updated.id ? updated : s)) } : current,
    )

  const addSection = async (event: FormEvent) => {
    event.preventDefault()
    if (!sectionName.trim()) return
    setAddingSection(true)
    try {
      const section = await courseApi.createSection(courseId, sectionName.trim())
      setData((current) =>
        current
          ? {
              ...current,
              section_count: current.section_count + 1,
              sections: [...current.sections, section].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true })),
            }
          : current,
      )
      setSectionName('')
      toast.success(`Section ${section.name} added`)
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setAddingSection(false)
    }
  }

  const toggleOpen = async (section: Section) => {
    try {
      const updated = await courseApi.updateSection(section.id, { is_open: !section.is_open })
      replaceSection(updated)
      toast.success(updated.is_open ? `Section ${updated.name} is open for joining` : `Section ${updated.name} is closed to new students`)
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  // Also covers navigating from one course to another while the new one loads.
  if (loading && (!course || course.id !== courseId)) return <LoadingState />
  if (error || !course) return <ErrorState message={error ?? 'Course not found'} onRetry={reload} />

  return (
    <>
      <PageHeader
        eyebrow={
          <Link to="/teacher/courses" className="inline-flex items-center gap-1 hover:text-zinc-900">
            <ArrowLeft className="size-3.5" /> Courses
          </Link>
        }
        title={course.name}
        description={
          <span className="inline-flex flex-wrap items-center gap-x-2">
            <span className="font-mono">{course.code}</span>
            <span aria-hidden>·</span>
            <span>
              {course.section_count} {course.section_count === 1 ? 'section' : 'sections'}, {course.student_count}{' '}
              {course.student_count === 1 ? 'student' : 'students'}
            </span>
          </span>
        }
        actions={
          <>
            <Button variant="secondary" onClick={() => setEditing(true)}>
              <Pencil /> Edit
            </Button>
            <Button variant="danger" onClick={() => setPending({ kind: 'delete-course' })}>
              <Trash2 /> Delete
            </Button>
          </>
        }
      />

      {course.description && <p className="-mt-2 mb-6 max-w-3xl text-sm whitespace-pre-line text-zinc-600">{course.description}</p>}

      <Card>
        <CardHeader title="Sections" description="Students join a section with its code. Close a section to stop new students joining." />
        <form onSubmit={addSection} className="flex gap-2 border-b border-zinc-200 p-3">
          <Input
            value={sectionName}
            onChange={(event) => setSectionName(event.target.value)}
            placeholder="Section name, e.g. 1 or A"
            aria-label="New section name"
            maxLength={60}
            className="max-w-xs"
          />
          <Button type="submit" variant="secondary" loading={addingSection} disabled={!sectionName.trim()}>
            <Plus /> Add section
          </Button>
        </form>

        {course.sections.length === 0 ? (
          <EmptyState icon={Layers} title="No sections yet" description="Add a section to get a join code for your students." />
        ) : (
          <Table>
            <THead>
              <tr>
                <TH>Section</TH>
                <TH>Join code</TH>
                <TH className="text-right">Students</TH>
                <TH>Status</TH>
                <TH className="hidden md:table-cell">Created</TH>
                <TH className="w-12">
                  <span className="sr-only">Actions</span>
                </TH>
              </tr>
            </THead>
            <TBody>
              {course.sections.map((section) => (
                <TR key={section.id}>
                  <TD className="font-medium text-zinc-900">{section.name}</TD>
                  <TD>
                    <CopyCode code={section.join_code} />
                  </TD>
                  <TD className="text-right tabular-nums">
                    <button className="hover:underline" onClick={() => setRosterSection(section)}>
                      {section.student_count}
                    </button>
                  </TD>
                  <TD>
                    <StatusBadge tone={section.is_open ? 'positive' : 'muted'}>{section.is_open ? 'Open' : 'Closed'}</StatusBadge>
                  </TD>
                  <TD className="hidden text-zinc-500 md:table-cell">{formatDate(section.created_at)}</TD>
                  <TD>
                    <DropdownMenu.Root>
                      <DropdownMenu.Trigger asChild>
                        <Button variant="ghost" size="icon" aria-label={`Actions for section ${section.name}`}>
                          <MoreHorizontal />
                        </Button>
                      </DropdownMenu.Trigger>
                      <DropdownMenu.Portal>
                        <DropdownMenu.Content align="end" sideOffset={4} className="z-50 w-52 rounded-md border border-zinc-200 bg-white p-1 shadow-md">
                          <DropdownMenu.Item className={menuItem} onSelect={() => setRosterSection(section)}>
                            View students
                          </DropdownMenu.Item>
                          <DropdownMenu.Item className={menuItem} onSelect={() => toggleOpen(section)}>
                            {section.is_open ? 'Close to new students' : 'Open for joining'}
                          </DropdownMenu.Item>
                          <DropdownMenu.Item className={menuItem} onSelect={() => setPending({ kind: 'regenerate', section })}>
                            Generate new join code
                          </DropdownMenu.Item>
                          <DropdownMenu.Separator className="my-1 h-px bg-zinc-200" />
                          <DropdownMenu.Item
                            className={`${menuItem} text-red-700 data-highlighted:bg-red-50`}
                            onSelect={() => setPending({ kind: 'delete-section', section })}
                          >
                            Delete section
                          </DropdownMenu.Item>
                        </DropdownMenu.Content>
                      </DropdownMenu.Portal>
                    </DropdownMenu.Root>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </Card>

      <CourseFormDialog
        open={editing}
        onOpenChange={setEditing}
        course={course}
        onSubmit={async (payload) => {
          const updated = await courseApi.update(course.id, payload)
          setData(() => updated)
          toast.success('Course updated')
        }}
      />

      <ConfirmDialog
        open={pending?.kind === 'delete-course'}
        onOpenChange={(open) => !open && setPending(null)}
        title={`Delete ${course.code}?`}
        description="This permanently deletes the course, its sections and all enrollments. Students will lose access to this course."
        confirmLabel="Delete course"
        destructive
        onConfirm={async () => {
          await courseApi.remove(course.id)
          toast.success(`Course ${course.code} deleted`)
          navigate('/teacher/courses', { replace: true })
        }}
      />

      <ConfirmDialog
        open={pending?.kind === 'delete-section'}
        onOpenChange={(open) => !open && setPending(null)}
        title={pending?.kind === 'delete-section' ? `Delete section ${pending.section.name}?` : ''}
        description="Students in this section will be unenrolled. This cannot be undone."
        confirmLabel="Delete section"
        destructive
        onConfirm={async () => {
          if (pending?.kind !== 'delete-section') return
          await courseApi.removeSection(pending.section.id)
          toast.success(`Section ${pending.section.name} deleted`)
          reload()
        }}
      />

      <ConfirmDialog
        open={pending?.kind === 'regenerate'}
        onOpenChange={(open) => !open && setPending(null)}
        title="Generate a new join code?"
        description="The current code will stop working immediately. Students already enrolled are not affected."
        confirmLabel="Generate code"
        onConfirm={async () => {
          if (pending?.kind !== 'regenerate') return
          replaceSection(await courseApi.regenerateCode(pending.section.id))
          toast.success('New join code generated')
        }}
      />

      <SectionRosterDialog
        section={rosterSection}
        courseCode={course.code}
        onClose={() => setRosterSection(null)}
        onRemoved={(sectionId) =>
          setData((current: CourseDetail | null) =>
            current
              ? {
                  ...current,
                  student_count: Math.max(0, current.student_count - 1),
                  sections: current.sections.map((s) => (s.id === sectionId ? { ...s, student_count: s.student_count - 1 } : s)),
                }
              : current,
          )
        }
      />
    </>
  )
}
