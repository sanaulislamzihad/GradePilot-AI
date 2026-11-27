import { Bot, ListChecks, Plus, X } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { EmptyState } from '@/components/ui/States'
import { useAiSlots } from '@/hooks/useAiSlots'
import { examApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import type { Question } from '@/types/api'
import { cn } from '@/utils/cn'
import { formatMarks, hasTwoDecimalsAtMost } from '@/utils/format'
import { leafQuestions, useExamWorkspace } from '../workspace'
import { StepCard } from './StepCard'

interface Row {
  key: number
  name: string
  description: string
  marks: string
}

let rowKey = 0
const newRow = (partial: Partial<Row> = {}): Row => ({ key: ++rowKey, name: '', description: '', marks: '', ...partial })

function RubricEditor({ question, canSuggest }: { question: Question; canSuggest: boolean }) {
  const { setExam, editable } = useExamWorkspace()
  const initial = question.rubric?.criteria.length
    ? question.rubric.criteria.map((c) => newRow({ name: c.name, description: c.description ?? '', marks: String(c.max_marks) }))
    : [newRow()]
  const [rows, setRows] = useState<Row[]>(initial)
  const [busy, setBusy] = useState<'draft' | 'approve' | 'ai' | null>(null)
  const [dirty, setDirty] = useState(false)

  const update = (key: number, patch: Partial<Row>) => {
    setRows((current) => current.map((r) => (r.key === key ? { ...r, ...patch } : r)))
    setDirty(true)
  }

  const parsed = rows.map((r) => ({ ...r, value: Number(r.marks) }))
  const rowInvalid = (r: (typeof parsed)[number]) =>
    !r.name.trim() || !r.marks.trim() || !(r.value > 0) || !hasTwoDecimalsAtMost(r.value)
  const anyInvalid = parsed.some(rowInvalid)
  const total = Math.round(parsed.reduce((s, r) => s + (r.value > 0 ? r.value : 0), 0) * 100) / 100
  const matches = question.marks !== null && total === question.marks
  const approved = question.rubric?.is_approved ?? false

  const suggest = async () => {
    setBusy('ai')
    try {
      setExam(await examApi.suggestRubric(question.id))
      toast.success(`AI rubric draft ready for ${question.full_label}. Review it before approving.`)
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  const save = async (approve: boolean) => {
    setBusy(approve ? 'approve' : 'draft')
    try {
      const criteria = parsed.map((r) => ({ name: r.name.trim(), description: r.description.trim() || null, max_marks: r.value }))
      setExam(await examApi.saveRubric(question.id, criteria, approve))
      setDirty(false)
      toast.success(approve ? `Rubric for ${question.full_label} approved` : `Rubric draft saved for ${question.full_label}`)
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
            <span className="ml-2 font-normal text-zinc-500">
              {question.marks === null ? 'No marks assigned' : `${formatMarks(question.marks)} marks`}
            </span>
          </p>
          <p className="mt-0.5 text-sm whitespace-pre-line text-zinc-600">{question.text || 'No question text'}</p>
        </div>
        {approved && !dirty ? (
          <StatusBadge tone={question.rubric && question.rubric.total === question.marks ? 'positive' : 'negative'}>
            {question.rubric && question.rubric.total === question.marks ? 'Approved' : 'Approved, total differs'}
          </StatusBadge>
        ) : question.rubric ? (
          <StatusBadge tone="warning">Draft</StatusBadge>
        ) : (
          <StatusBadge tone="negative">Missing</StatusBadge>
        )}
      </div>

      {question.model_answer && (
        <details className="rounded-md border border-zinc-200 text-sm">
          <summary className="cursor-pointer px-3 py-2 text-[13px] text-zinc-600 select-none hover:bg-zinc-50">Model answer</summary>
          <p className="border-t border-zinc-100 px-3 py-2 whitespace-pre-line text-zinc-700">{question.model_answer.content}</p>
        </details>
      )}

      <div className="space-y-2">
        <div className="hidden grid-cols-[1fr_1.4fr_5.5rem_2.25rem] gap-2 px-0.5 text-xs font-medium text-zinc-500 sm:grid">
          <span>Criterion</span>
          <span>What earns the marks</span>
          <span className="text-right">Marks</span>
          <span />
        </div>
        {rows.map((row, index) => (
          <div key={row.key} className="grid gap-2 sm:grid-cols-[1fr_1.4fr_5.5rem_2.25rem]">
            <Input value={row.name} onChange={(e) => update(row.key, { name: e.target.value })} placeholder="e.g. Correct definition" aria-label={`Criterion ${index + 1} name`} maxLength={200} disabled={!editable} />
            <Input value={row.description} onChange={(e) => update(row.key, { description: e.target.value })} placeholder="Optional guidance for markers" aria-label={`Criterion ${index + 1} description`} maxLength={2000} disabled={!editable} />
            <Input type="number" inputMode="decimal" min="0" step="any" value={row.marks} onChange={(e) => update(row.key, { marks: e.target.value })} aria-label={`Criterion ${index + 1} marks`} className="text-right tabular-nums" disabled={!editable} />
            {editable ? (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  setRows((r) => r.filter((x) => x.key !== row.key))
                  setDirty(true)
                }}
                disabled={rows.length === 1}
                aria-label={`Remove criterion ${index + 1}`}
              >
                <X />
              </Button>
            ) : (
              <span />
            )}
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          {editable && canSuggest && !approved && !dirty && question.marks !== null && (
            <Button variant="ghost" size="sm" onClick={suggest} loading={busy === 'ai'}>
              <Bot /> Suggest with AI
            </Button>
          )}
          {editable && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setRows((r) => [...r, newRow()])
                setDirty(true)
              }}
              disabled={rows.length >= 30}
            >
              <Plus /> Add criterion
            </Button>
          )}
          <span className={cn('text-sm tabular-nums', matches ? 'text-zinc-500' : 'text-red-700')}>
            Total {formatMarks(total)} / {formatMarks(question.marks)}
          </span>
        </div>
        {editable && (
          <div className="flex justify-end gap-2">
            {dirty && (
              <Button size="sm" variant="secondary" onClick={() => save(false)} loading={busy === 'draft'} disabled={anyInvalid}>
                Save draft
              </Button>
            )}
            {(dirty || !approved) && (
              <Button
                size="sm"
                onClick={() => save(true)}
                loading={busy === 'approve'}
                disabled={anyInvalid || !matches}
                title={!matches ? 'The criteria must add up to the question marks' : undefined}
              >
                Approve rubric
              </Button>
            )}
          </div>
        )}
      </div>
      {anyInvalid && dirty && <p className="text-[13px] text-red-700">Every criterion needs a name and positive marks.</p>}
    </div>
  )
}

export function RubricsStep() {
  const { exam } = useExamWorkspace()
  const slots = useAiSlots()
  const leaves = leafQuestions(exam)
  const approvedCount = leaves.filter((q) => q.rubric?.is_approved && q.rubric.total === q.marks).length

  return (
    <StepCard
      step="rubrics"
      title="Marking rubrics"
      description={`Break each question's marks into criteria. The criteria must add up to the question's marks. ${approvedCount} of ${leaves.length} approved.`}
    >
      {leaves.length === 0 ? (
        <EmptyState icon={ListChecks} title="No questions yet" description="Add questions and marks before building rubrics." />
      ) : (
        <div className="divide-y divide-zinc-100">
          {leaves.map((question) => (
            <RubricEditor
              key={`${question.id}:${question.rubric?.approved_at ?? ''}:${question.rubric?.criteria.map((c) => c.id).join() ?? ''}:${question.marks}`}
              question={question}
              canSuggest={slots.has('evaluator')}
            />
          ))}
        </div>
      )}
    </StepCard>
  )
}
