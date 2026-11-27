import { useState } from 'react'
import { toast } from 'sonner'
import { StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Select, Textarea } from '@/components/ui/Input'
import { processingApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import type { AnswerStatus, ExtractionView } from '@/types/api'
import { formatMarks } from '@/utils/format'

const sourceLabel = { pdf_text: 'PDF text', ai_ocr: 'Read by AI', teacher: 'Corrected by you' } as const
const EDITABLE = ['ocr_review_required', 'ready_for_evaluation', 'teacher_review_required', 'failed']

interface Draft {
  text: string
  status: AnswerStatus
}

interface ExtractionEditorProps {
  submissionId: string
  view: ExtractionView
  onSaved: (view: ExtractionView, confirmed: boolean) => void
}

export function ExtractionEditor({ submissionId, view, onSaved }: ExtractionEditorProps) {
  const editable = EDITABLE.includes(view.status)
  const initial = Object.fromEntries(view.answers.map((a) => [a.question_id, { text: a.text, status: a.status }])) as Record<string, Draft>
  const [drafts, setDrafts] = useState(initial)
  const [busy, setBusy] = useState<'save' | 'confirm' | null>(null)
  const changed = view.answers.filter(
    (a) => drafts[a.question_id]!.text !== a.text || drafts[a.question_id]!.status !== a.status,
  )
  const reviewing = view.status === 'ocr_review_required'

  const save = async (confirm: boolean) => {
    setBusy(confirm ? 'confirm' : 'save')
    try {
      // Confirming sends every answer so the teacher's view is what gets marked.
      const items = (confirm ? view.answers : changed).map((a) => ({ question_id: a.question_id, ...drafts[a.question_id]! }))
      const updated = await processingApi.correctAnswers(submissionId, items, confirm)
      onSaved(updated, confirm)
      toast.success(confirm ? 'Answers confirmed' : 'Corrections saved')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card>
      <CardHeader
        title="Extracted answers"
        description="What was read from the script, per question. Correct any mistakes before marking; corrected text is used as written."
      />
      {view.extraction_notes && (
        <pre className="mx-5 mt-4 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 font-sans text-[13px] whitespace-pre-wrap text-zinc-700">
          {view.extraction_notes}
        </pre>
      )}
      <ul className="divide-y divide-zinc-100">
        {view.answers.map((answer) => {
          const draft = drafts[answer.question_id]!
          return (
            <li key={answer.question_id} className="space-y-2 px-5 py-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-zinc-900">
                    <span className="font-mono">{answer.label}</span>
                    <span className="ml-2 font-normal text-zinc-500">{formatMarks(answer.max_marks)} marks</span>
                  </p>
                  <p className="line-clamp-2 text-[13px] text-zinc-500">{answer.question_text}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                  {answer.needs_review && <StatusBadge tone="warning">Check this</StatusBadge>}
                  <span>{sourceLabel[answer.source]}</span>
                  {answer.source === 'ai_ocr' && <span className="tabular-nums">· {Math.round(answer.confidence * 100)}% confident</span>}
                  {answer.pages.length > 0 && <span>· page {answer.pages.join(', ')}</span>}
                </div>
              </div>
              {answer.unreadable_notes.length > 0 && (
                <ul className="list-inside list-disc text-[13px] text-amber-800">
                  {answer.unreadable_notes.map((note) => (
                    <li key={note}>Could not read: {note}</li>
                  ))}
                </ul>
              )}
              <div className="flex flex-col gap-2 sm:flex-row">
                <Textarea
                  value={draft.text}
                  onChange={(e) => setDrafts((d) => ({ ...d, [answer.question_id]: { ...d[answer.question_id]!, text: e.target.value } }))}
                  rows={Math.min(8, Math.max(3, draft.text.split('\n').length + 1))}
                  placeholder={draft.status === 'missing' ? 'No answer found' : 'Answer text'}
                  aria-label={`Answer text for question ${answer.label}`}
                  disabled={!editable || draft.status !== 'answered'}
                  className="flex-1"
                />
                <Select
                  value={draft.status}
                  onChange={(e) => setDrafts((d) => ({ ...d, [answer.question_id]: { ...d[answer.question_id]!, status: e.target.value as AnswerStatus } }))}
                  aria-label={`Status of question ${answer.label}`}
                  disabled={!editable}
                  className="sm:w-40"
                >
                  <option value="answered">Answered</option>
                  <option value="missing">Not answered</option>
                  <option value="unreadable">Unreadable — I will mark it</option>
                </Select>
              </div>
            </li>
          )
        })}
      </ul>
      {editable && (
        <div className="flex flex-wrap justify-end gap-2 border-t border-zinc-200 px-5 py-3">
          {changed.length > 0 && !reviewing && (
            <Button variant="secondary" onClick={() => save(false)} loading={busy === 'save'}>
              Save corrections
            </Button>
          )}
          {reviewing && (
            <Button onClick={() => save(true)} loading={busy === 'confirm'}>
              Confirm answers and mark
            </Button>
          )}
        </div>
      )}
    </Card>
  )
}
