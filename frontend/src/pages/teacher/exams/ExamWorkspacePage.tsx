import { ArrowLeft, Check, Lock, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, Navigate, NavLink, useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/Dialog'
import { PageHeader } from '@/components/ui/PageHeader'
import { ErrorState, LoadingState } from '@/components/ui/States'
import { useAsync } from '@/hooks/useAsync'
import { examApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import type { ExamDetail } from '@/types/api'
import { cn } from '@/utils/cn'
import { examTypeLabel } from '@/utils/format'
import { ExamStatusBadge } from './ExamStatusBadge'
import { AnswersStep } from './steps/AnswersStep'
import { DetailsStep } from './steps/DetailsStep'
import { MarksStep } from './steps/MarksStep'
import { PaperStep } from './steps/PaperStep'
import { PublishStep } from './steps/PublishStep'
import { QuestionsStep } from './steps/QuestionsStep'
import { RubricsStep } from './steps/RubricsStep'
import { ExamWorkspaceContext, stepDone, steps, type StepKey } from './workspace'

const stepComponents: Record<StepKey, () => React.JSX.Element> = {
  details: DetailsStep,
  paper: PaperStep,
  questions: QuestionsStep,
  marks: MarksStep,
  answers: AnswersStep,
  rubrics: RubricsStep,
  publish: PublishStep,
}

export default function ExamWorkspacePage() {
  const { examId = '', step } = useParams()
  const navigate = useNavigate()
  const { data: exam, error, loading, reload, setData } = useAsync(() => examApi.get(examId), `exam:${examId}`)
  const [deleting, setDeleting] = useState(false)
  const [unpublishing, setUnpublishing] = useState(false)

  const workspace = useMemo(
    () => (exam ? { exam, setExam: (next: ExamDetail) => setData(() => next), editable: exam.status === 'draft' } : null),
    [exam, setData],
  )

  if (loading && (!exam || exam.id !== examId)) return <LoadingState />
  if (error || !exam || !workspace) return <ErrorState message={error ?? 'Exam not found'} onRetry={reload} />

  if (!step || !(step in stepComponents)) {
    return <Navigate to={`/teacher/exams/${exam.id}/${exam.status === 'published' ? 'publish' : 'details'}`} replace />
  }
  const StepComponent = stepComponents[step as StepKey]

  const unpublish = async () => {
    setUnpublishing(true)
    try {
      const updated = await examApi.unpublish(exam.id)
      setData(() => updated)
      toast.success('Exam unpublished. You can edit it again.')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setUnpublishing(false)
    }
  }

  return (
    <ExamWorkspaceContext.Provider value={workspace}>
      <PageHeader
        eyebrow={
          <Link to="/teacher/exams" className="inline-flex items-center gap-1 hover:text-zinc-900">
            <ArrowLeft className="size-3.5" /> My Exams
          </Link>
        }
        title={exam.title}
        description={
          <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
            <ExamStatusBadge status={exam.status} />
            <span>{examTypeLabel[exam.exam_type]}</span>
            {exam.course_code && (
              <>
                <span aria-hidden>·</span>
                <span className="font-mono">{exam.course_code}</span>
                {exam.section_name && <span>Section {exam.section_name}</span>}
              </>
            )}
          </span>
        }
        actions={
          exam.status === 'draft' && (
            <Button variant="danger" onClick={() => setDeleting(true)}>
              <Trash2 /> Delete
            </Button>
          )
        }
      />

      {exam.status === 'published' && (
        <div className="mb-6 flex flex-col gap-3 rounded-lg border border-zinc-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="flex items-center gap-2 text-sm text-zinc-700">
            <Lock className="size-4 text-zinc-500" aria-hidden />
            {exam.submission_count > 0
              ? 'This exam is published and locked. Students have submitted scripts, so it can no longer be changed.'
              : 'This exam is published and locked. Unpublish it to make changes.'}
          </p>
          {exam.submission_count === 0 && (
            <Button variant="secondary" size="sm" onClick={unpublish} loading={unpublishing}>
              Unpublish to edit
            </Button>
          )}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[200px_1fr]">
        <nav aria-label="Exam setup steps" className="lg:sticky lg:top-8 lg:self-start">
          <ol className="flex gap-1 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0">
            {steps.map((s, index) => {
              const done = stepDone(exam, s.key)
              return (
                <li key={s.key} className="shrink-0">
                  <NavLink
                    to={`/teacher/exams/${exam.id}/${s.key}`}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm whitespace-nowrap transition-colors',
                        isActive ? 'bg-white font-medium text-zinc-900 ring-1 ring-zinc-200' : 'text-zinc-600 hover:bg-white/70',
                      )
                    }
                  >
                    <span
                      className={cn(
                        'flex size-5 shrink-0 items-center justify-center rounded-full border text-[11px] font-medium',
                        done ? 'border-zinc-900 bg-zinc-900 text-white' : 'border-zinc-300 text-zinc-500',
                      )}
                      aria-hidden
                    >
                      {done ? <Check className="size-3" strokeWidth={3} /> : index + 1}
                    </span>
                    {s.label}
                    {done && <span className="sr-only">(complete)</span>}
                  </NavLink>
                </li>
              )
            })}
          </ol>
        </nav>

        <div className="min-w-0">
          <StepComponent />
        </div>
      </div>

      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title="Delete this exam?"
        description="The exam, its questions, model answers, rubrics and uploaded files are permanently deleted."
        confirmLabel="Delete exam"
        destructive
        onConfirm={async () => {
          await examApi.remove(exam.id)
          toast.success('Exam deleted')
          navigate('/teacher/exams', { replace: true })
        }}
      />
    </ExamWorkspaceContext.Provider>
  )
}
