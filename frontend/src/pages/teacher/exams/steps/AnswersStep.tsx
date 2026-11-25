import { BookOpenCheck } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { FileUpload } from '@/components/FileUpload'
import { StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { CardBody } from '@/components/ui/Card'
import { Textarea } from '@/components/ui/Input'
import { EmptyState } from '@/components/ui/States'
import { examApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import type { ModelAnswerUploadResult, Question } from '@/types/api'
import { formatMarks } from '@/utils/format'
import { leafQuestions, useExamWorkspace } from '../workspace'
import { DocumentCard } from './DocumentCard'
import { StepCard } from './StepCard'

function AnswerStatus({ question }: { question: Question }) {
  const answer = question.model_answer
  if (!answer) return <StatusBadge tone="negative">Missing</StatusBadge>
  if (answer.is_approved) return <StatusBadge tone="positive">Approved</StatusBadge>
  return <StatusBadge tone="warning">{answer.source === 'uploaded' ? 'Imported, needs review' : 'Draft'}</StatusBadge>
}

function AnswerEditor({ question }: { question: Question }) {
  const { setExam, editable } = useExamWorkspace()
  const saved = question.model_answer?.content ?? ''
  const [content, setContent] = useState(saved)
  const [busy, setBusy] = useState<'draft' | 'approve' | 'remove' | null>(null)
  const dirty = content.trim() !== saved
  const approved = question.model_answer?.is_approved ?? false

  const save = async (approve: boolean) => {
    if (!content.trim()) {
      toast.error('Write the model answer first')
      return
    }
    setBusy(approve ? 'approve' : 'draft')
    try {
      setExam(await examApi.saveModelAnswer(question.id, content.trim(), approve))
      toast.success(approve ? `Model answer ${question.full_label} approved` : `Draft saved for ${question.full_label}`)
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  const remove = async () => {
    setBusy('remove')
    try {
      setExam(await examApi.removeModelAnswer(question.id))
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-3 px-5 py-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium text-zinc-900">
            <span className="font-mono">{question.full_label}</span>
            <span className="ml-2 font-normal text-zinc-500">{formatMarks(question.marks)} marks</span>
          </p>
          <p className="mt-0.5 text-sm whitespace-pre-line text-zinc-600">{question.text || 'No question text'}</p>
        </div>
        <AnswerStatus question={question} />
      </div>
      <Textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={4}
        placeholder="Write the expected answer, including key points, accepted alternatives and any working."
        aria-label={`Model answer for question ${question.full_label}`}
        disabled={!editable}
      />
      {editable && (
        <div className="flex flex-wrap justify-end gap-2">
          {question.model_answer && !dirty && (
            <Button size="sm" variant="ghost" onClick={remove} loading={busy === 'remove'}>
              Remove
            </Button>
          )}
          {dirty && (
            <Button size="sm" variant="secondary" onClick={() => save(false)} loading={busy === 'draft'}>
              Save draft
            </Button>
          )}
          {(dirty || !approved) && (
            <Button size="sm" onClick={() => save(true)} loading={busy === 'approve'} disabled={!content.trim()}>
              {dirty ? 'Save and approve' : 'Approve'}
            </Button>
          )}
        </div>
      )}
    </div>
  )
}

function UploadReport({ report }: { report: ModelAnswerUploadResult }) {
  const rows: [string, string[]][] = [
    ['Filled in (needs your review)', report.matched],
    ['Kept because already approved', report.skipped_approved],
    ['No answer found in the file', report.unmatched_questions],
    ['Sections in the file with no matching question', report.unused_sections],
  ]
  return (
    <dl className="grid gap-2 rounded-lg border border-zinc-200 bg-zinc-50/60 p-4 text-sm sm:grid-cols-2">
      {rows.map(([label, items]) => (
        <div key={label}>
          <dt className="text-xs text-zinc-500">{label}</dt>
          <dd className="mt-0.5 font-mono text-zinc-900">{items.length ? items.join(', ') : '—'}</dd>
        </div>
      ))}
    </dl>
  )
}

export function AnswersStep() {
  const { exam, setExam, editable } = useExamWorkspace()
  const leaves = leafQuestions(exam)
  const [uploading, setUploading] = useState(false)
  const [overwrite, setOverwrite] = useState(false)
  const [report, setReport] = useState<ModelAnswerUploadResult | null>(null)
  const answerDoc = exam.documents.find((d) => d.kind === 'model_answer')
  const approvedCount = leaves.filter((q) => q.model_answer?.is_approved).length

  const onFile = async (file: File) => {
    setUploading(true)
    try {
      const result = await examApi.uploadModelAnswers(exam.id, file, overwrite)
      setExam(result.exam)
      setReport(result)
      toast.success(
        result.matched.length
          ? `Filled in ${result.matched.length} answer${result.matched.length === 1 ? '' : 's'}. Review and approve each one.`
          : 'File uploaded, but no answers matched the question numbers.',
      )
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setUploading(false)
    }
  }

  return (
    <StepCard
      step="answers"
      title="Model answers"
      description={`Every gradable question needs an approved model answer. ${approvedCount} of ${leaves.length} approved.`}
    >
      {leaves.length === 0 ? (
        <EmptyState icon={BookOpenCheck} title="No questions yet" description="Add questions before writing model answers." />
      ) : (
        <>
          <CardBody className="space-y-3 border-b border-zinc-200">
            <p className="text-sm text-zinc-700">
              Have a model answer document? Upload it to fill in answers by question number (for example
              “1.”, “2(a)”). Imported answers stay unapproved until you review them.
            </p>
            {answerDoc && <DocumentCard examId={exam.id} document={answerDoc} />}
            {editable && (
              <>
                <FileUpload accept={['.pdf', '.docx']} maxBytes={20 * 1024 * 1024} onFile={onFile} busy={uploading} />
                <label className="flex items-center gap-2 text-[13px] text-zinc-600">
                  <input type="checkbox" className="accent-zinc-900" checked={overwrite} onChange={(e) => setOverwrite(e.target.checked)} />
                  Also replace answers I have already approved
                </label>
              </>
            )}
            {report && <UploadReport report={report} />}
          </CardBody>
          <div className="divide-y divide-zinc-100">
            {leaves.map((question) => (
              <AnswerEditor key={`${question.id}:${question.model_answer?.updated_at ?? 'none'}`} question={question} />
            ))}
          </div>
        </>
      )}
    </StepCard>
  )
}
