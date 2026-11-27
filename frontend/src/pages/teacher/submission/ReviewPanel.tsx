import { Check, History, Quote, RotateCcw, ShieldCheck, X } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { FormField } from '@/components/ui/FormField'
import { Input, Textarea } from '@/components/ui/Input'
import { useAsync } from '@/hooks/useAsync'
import { reviewApi, type QuestionReviewPayload } from '@/services/api'
import { errorMessage } from '@/services/http'
import type { Evaluation, EvaluationQuestion, SubmissionDetail } from '@/types/api'
import { cn } from '@/utils/cn'
import { formatDateTime, formatMarks, formatRelative, hasTwoDecimalsAtMost } from '@/utils/format'
import { flagText, reviewStatusLabel, verificationLabel } from '@/utils/reviewFlags'

type Draft = Record<string, { criteria: Record<string, string>; question: string; comment: string }>

function initialDraft(evaluation: Evaluation): Draft {
  return Object.fromEntries(
    evaluation.questions.map((q) => [
      q.question_id,
      {
        criteria: Object.fromEntries(q.criteria.map((c) => [c.id, c.teacher_awarded === null ? '' : String(c.teacher_awarded)])),
        question: q.teacher_awarded === null ? '' : String(q.teacher_awarded),
        comment: q.teacher_comment ?? '',
      },
    ]),
  )
}

const parse = (raw: string): number | null => (raw.trim() === '' ? null : Number(raw))
const invalid = (raw: string, max: number) => {
  const v = parse(raw)
  return v !== null && (!Number.isFinite(v) || v < 0 || v > max || !hasTwoDecimalsAtMost(v))
}

function Flags({ flags }: { flags: string[] }) {
  if (!flags.length) return null
  return (
    <span className="flex flex-wrap gap-1.5">
      {flags.map((flag) => (
        <StatusBadge key={flag} tone={flag === 'missing_answer' ? 'muted' : 'warning'}>
          {flagText[flag] ?? flag}
        </StatusBadge>
      ))}
    </span>
  )
}

function Checks({ question }: { question: EvaluationQuestion }) {
  const v = question.verification
  const m = question.math_check
  if (!v && !m && question.similarity === null) return null
  return (
    <div className="space-y-2 rounded-md border border-zinc-200 bg-white px-3 py-2.5 text-[13px]">
      <p className="text-xs font-medium tracking-wide text-zinc-500 uppercase">Independent checks</p>
      {v && (
        <div className="space-y-1">
          <p className="flex flex-wrap items-center gap-2 text-zinc-800">
            <StatusBadge tone={v.verdict === 'agrees' ? 'positive' : v.verdict === 'disagrees' ? 'warning' : 'negative'}>
              {v.verdict === 'agrees' ? 'Verifier agrees' : v.verdict === 'disagrees' ? 'Verifier disagrees' : 'Verifier failed'}
            </StatusBadge>
            {v.suggested_awarded !== null && <span>Suggests {formatMarks(v.suggested_awarded)} / {formatMarks(question.max_marks)}</span>}
            <span className="text-zinc-400">
              {v.provider}/{v.model}
              {v.same_model_as_evaluator && ' · same model as the evaluator'}
            </span>
          </p>
          {v.rubric_followed === false && <p className="text-amber-800">The verifier thinks the rubric was not followed.</p>}
          {v.evidence_supports_marks === false && <p className="text-amber-800">The verifier thinks the evidence does not support the marks.</p>}
          {v.missed_valid_concepts.length > 0 && <p className="text-zinc-700">Missed valid points: {v.missed_valid_concepts.join('; ')}</p>}
          {v.unsupported_assumptions.length > 0 && <p className="text-zinc-700">Unsupported assumptions: {v.unsupported_assumptions.join('; ')}</p>}
          {v.criterion_notes.filter((n) => !n.fair).map((n) => (
            <p key={n.criterion} className="text-zinc-700">
              {n.criterion}: would give {formatMarks(n.suggested_awarded)} — {n.note}
            </p>
          ))}
          {v.comment && <p className="text-zinc-600">{v.comment}</p>}
        </div>
      )}
      {m && (
        <div className="space-y-0.5">
          <p className="text-zinc-800">
            SymPy: <span className={cn('font-medium', m.status === 'match' ? 'text-zinc-900' : 'text-amber-800')}>{m.status}</span>
            {m.expected && (
              <span className="font-mono text-xs text-zinc-500">
                {' '}
                · expected {m.expected}
                {m.student && ` · student ${m.student}`}
              </span>
            )}
          </p>
          <p className="text-zinc-600">{m.detail}</p>
          {m.step_errors.map((e) => (
            <p key={e.line} className="font-mono text-xs text-amber-800">
              line {e.line}: {e.text}
            </p>
          ))}
        </div>
      )}
      {question.similarity !== null && (
        <p className="text-zinc-700">Similarity to the model answer: {Math.round(question.similarity * 100)}% (signal only)</p>
      )}
    </div>
  )
}

interface QuestionReviewProps {
  question: EvaluationQuestion
  draft: Draft[string]
  editable: boolean
  onChange: (draft: Draft[string]) => void
}

function QuestionReview({ question, draft, editable, onChange }: QuestionReviewProps) {
  const ungraded = question.awarded === null
  return (
    <details className="group" open={question.flags.some((f) => f !== 'missing_answer') || ungraded}>
      <summary className="flex cursor-pointer items-center justify-between gap-4 px-5 py-3.5 select-none hover:bg-zinc-50">
        <span className="flex min-w-0 flex-wrap items-center gap-3">
          <span className="font-mono text-sm font-medium text-zinc-900">{question.label}</span>
          <Flags flags={question.flags} />
        </span>
        <span className="shrink-0 text-right text-sm tabular-nums">
          <span className="font-semibold text-zinc-900">{question.final_awarded === null ? '—' : formatMarks(question.final_awarded)}</span>
          <span className="text-zinc-500"> / {formatMarks(question.max_marks)}</span>
          {question.final_awarded !== question.awarded && (
            <span className="block text-xs text-zinc-400">AI: {question.awarded === null ? 'not marked' : formatMarks(question.awarded)}</span>
          )}
        </span>
      </summary>
      <div className="space-y-4 border-t border-zinc-100 bg-zinc-50/40 px-5 py-4">
        {question.criteria.length > 0 && (
          <ul className="space-y-3">
            {question.criteria.map((criterion) => {
              const raw = draft.criteria[criterion.id] ?? ''
              return (
                <li key={criterion.id} className="rounded-md border border-zinc-200 bg-white px-3 py-2.5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-zinc-900">{criterion.name}</p>
                      <p className="text-xs text-zinc-500 tabular-nums">
                        AI {formatMarks(criterion.awarded)} / {formatMarks(criterion.max_marks)}
                      </p>
                    </div>
                    <label className="flex items-center gap-2 text-xs text-zinc-500">
                      Your mark
                      <Input
                        type="number"
                        inputMode="decimal"
                        step="any"
                        min="0"
                        value={raw}
                        placeholder={formatMarks(criterion.awarded)}
                        onChange={(e) => onChange({ ...draft, criteria: { ...draft.criteria, [criterion.id]: e.target.value } })}
                        aria-label={`Your mark for ${question.label} ${criterion.name}`}
                        aria-invalid={invalid(raw, criterion.max_marks) || undefined}
                        className="h-8 w-20 text-right tabular-nums"
                        disabled={!editable}
                      />
                    </label>
                  </div>
                  {criterion.explanation && <p className="mt-1 text-[13px] text-zinc-600">{criterion.explanation}</p>}
                  {criterion.evidence.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {criterion.evidence.map((e) => (
                        <li key={e.quote} className="flex items-start gap-1.5 text-[13px]">
                          <Quote className="mt-0.5 size-3.5 shrink-0 text-zinc-400" aria-hidden />
                          <span className={cn('italic', e.found_in_answer ? 'text-zinc-700' : 'text-red-700')}>“{e.quote}”</span>
                          {e.found_in_answer ? (
                            <Check className="mt-0.5 size-3.5 shrink-0 text-zinc-500" aria-label="Found in the answer" />
                          ) : (
                            <X className="mt-0.5 size-3.5 shrink-0 text-red-700" aria-label="Not found in the answer" />
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                  {criterion.missing_concepts.length > 0 && (
                    <p className="mt-1.5 text-[13px] text-zinc-500">Missing: {criterion.missing_concepts.join('; ')}</p>
                  )}
                </li>
              )
            })}
          </ul>
        )}

        <Checks question={question} />

        {question.feedback && (
          <div>
            <p className="text-xs font-medium text-zinc-500">AI feedback for the student</p>
            <p className="mt-0.5 text-sm text-zinc-800">{question.feedback}</p>
          </div>
        )}
        {question.answer_text && (
          <details>
            <summary className="cursor-pointer text-xs font-medium text-zinc-500 select-none">Student’s answer</summary>
            <p className="mt-1 text-sm whitespace-pre-line text-zinc-700">{question.answer_text}</p>
          </details>
        )}

        <div className="grid gap-3 sm:grid-cols-[10rem_1fr]">
          <FormField
            label="Question mark"
            hint={ungraded ? 'Required: the AI did not mark this.' : 'Optional: replaces the criteria total.'}
            error={invalid(draft.question, question.max_marks) ? `Between 0 and ${formatMarks(question.max_marks)}` : undefined}
          >
            <Input
              type="number"
              inputMode="decimal"
              step="any"
              min="0"
              value={draft.question}
              onChange={(e) => onChange({ ...draft, question: e.target.value })}
              placeholder={ungraded ? '' : formatMarks(question.awarded)}
              disabled={!editable}
            />
          </FormField>
          <FormField label="Your comment" optional>
            <Textarea rows={2} value={draft.comment} onChange={(e) => onChange({ ...draft, comment: e.target.value })} disabled={!editable} />
          </FormField>
        </div>
      </div>
    </details>
  )
}

function HistoryList({ evaluationId, refreshKey }: { evaluationId: string; refreshKey: string }) {
  const { data } = useAsync(() => reviewApi.history(evaluationId), `history:${evaluationId}:${refreshKey}`)
  if (!data || data.length === 0) return null
  return (
    <details className="border-t border-zinc-200">
      <summary className="flex cursor-pointer items-center gap-2 px-5 py-3 text-sm font-medium text-zinc-700 select-none hover:bg-zinc-50">
        <History className="size-4" aria-hidden /> Review history ({data.length})
      </summary>
      <ul className="divide-y divide-zinc-100 border-t border-zinc-100">
        {data.map((entry) => (
          <li key={entry.created_at + entry.action} className="px-5 py-2.5 text-[13px]">
            <p className="text-zinc-800">
              {entry.summary}
              <span className="text-zinc-400" title={formatDateTime(entry.created_at)}>
                {' '}
                · {entry.actor_name ?? 'Someone'} · {formatRelative(entry.created_at)}
              </span>
            </p>
            {entry.changes.map((c, i) => (
              <p key={i} className="text-xs text-zinc-500">
                {c.question}: {c.field} {c.old ?? '—'} → {c.new ?? '—'}
              </p>
            ))}
          </li>
        ))}
      </ul>
    </details>
  )
}

interface ReviewPanelProps {
  evaluation: Evaluation
  submission: SubmissionDetail
  onEvaluation: (evaluation: Evaluation) => void
  onSubmission: (submission: SubmissionDetail) => void
}

export function ReviewPanel({ evaluation, submission, onEvaluation, onSubmission }: ReviewPanelProps) {
  const [draft, setDraft] = useState<Draft>(() => initialDraft(evaluation))
  const [overall, setOverall] = useState(evaluation.teacher_comment ?? '')
  const [busy, setBusy] = useState<string | null>(null)
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const editable = evaluation.review_status === 'pending' && submission.status === 'teacher_review_required'

  const payload: QuestionReviewPayload[] = evaluation.questions.map((q) => ({
    question_id: q.question_id,
    criteria: q.criteria.map((c) => ({ criterion_id: c.id, teacher_awarded: parse(draft[q.question_id]!.criteria[c.id] ?? '') })),
    teacher_awarded: parse(draft[q.question_id]!.question),
    teacher_comment: draft[q.question_id]!.comment.trim() || null,
  }))
  const original = initialDraft(evaluation)
  const dirty = JSON.stringify(draft) !== JSON.stringify(original) || overall !== (evaluation.teacher_comment ?? '')
  const hasInvalid = evaluation.questions.some(
    (q) => invalid(draft[q.question_id]!.question, q.max_marks) || q.criteria.some((c) => invalid(draft[q.question_id]!.criteria[c.id] ?? '', c.max_marks)),
  )

  const act = async (name: string, fn: () => Promise<void>) => {
    setBusy(name)
    try {
      await fn()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  const save = () => act('save', async () => {
    const updated = await reviewApi.save(evaluation.id, payload, overall)
    onEvaluation(updated)
    toast.success('Review saved. Marks recalculated.')
  })

  const approve = () => act('approve', async () => {
    let current = evaluation
    if (dirty) current = await reviewApi.save(evaluation.id, payload, overall)
    const approved = await reviewApi.approve(current.id)
    onEvaluation(approved)
    onSubmission({ ...submission, status: 'approved' })
    toast.success(`Marks approved: ${formatMarks(approved.final_total)} / ${formatMarks(approved.total_max)}`)
  })

  return (
    <Card>
      <CardHeader
        title="Review marks"
        description={`AI suggestions from ${evaluation.provider}/${evaluation.model}, run ${evaluation.run_number}. ${verificationLabel[evaluation.verification_status]}. Your marks replace the AI's; the final total is calculated on the server.`}
        action={
          <div className="text-right">
            <p className="text-xl font-semibold text-zinc-900 tabular-nums">
              {evaluation.final_total === null ? '—' : formatMarks(evaluation.final_total)}
              <span className="text-sm font-normal text-zinc-500"> / {formatMarks(evaluation.total_max)}</span>
            </p>
            <p className="text-xs text-zinc-500 tabular-nums">AI {evaluation.total_awarded === null ? '—' : formatMarks(evaluation.total_awarded)}</p>
            <div className="mt-1">
              <StatusBadge tone={evaluation.review_status === 'approved' ? 'positive' : 'warning'}>
                {reviewStatusLabel[evaluation.review_status]}
              </StatusBadge>
            </div>
          </div>
        }
      />
      {evaluation.flags.some((f) => f !== 'missing_answer') && (
        <div className="border-b border-zinc-100 px-5 py-3">
          <Flags flags={evaluation.flags.filter((f) => f !== 'missing_answer')} />
        </div>
      )}
      {evaluation.review_status === 'approved' && (
        <p className="border-b border-zinc-100 px-5 py-3 text-sm text-zinc-700">
          Approved by {evaluation.reviewed_by ?? 'you'} {formatDateTime(evaluation.reviewed_at)}.
        </p>
      )}

      <div className="divide-y divide-zinc-100">
        {evaluation.questions.map((q) => (
          <QuestionReview
            key={q.question_id}
            question={q}
            draft={draft[q.question_id]!}
            editable={editable}
            onChange={(d) => setDraft((all) => ({ ...all, [q.question_id]: d }))}
          />
        ))}
      </div>

      <div className="space-y-3 border-t border-zinc-200 px-5 py-4">
        <FormField label="Overall comment" optional>
          <Textarea rows={2} value={overall} onChange={(e) => setOverall(e.target.value)} disabled={!editable} />
        </FormField>
        <div className="flex flex-wrap justify-end gap-2">
          {editable && (
            <>
              <Button variant="ghost" onClick={() => act('verify', async () => onSubmission(await reviewApi.verify(evaluation.id)))} loading={busy === 'verify'}>
                <ShieldCheck /> Check again
              </Button>
              <Button variant="danger" onClick={() => setRejecting(true)}>
                Reject and re-mark
              </Button>
              {dirty && (
                <Button variant="secondary" onClick={save} loading={busy === 'save'} disabled={hasInvalid}>
                  Save changes
                </Button>
              )}
              <Button onClick={approve} loading={busy === 'approve'} disabled={hasInvalid}>
                <Check /> {dirty ? 'Save and approve' : 'Approve marks'}
              </Button>
            </>
          )}
          {evaluation.review_status === 'approved' && submission.status === 'approved' && (
            <Button
              variant="secondary"
              onClick={() => act('reopen', async () => {
                onEvaluation(await reviewApi.reopen(evaluation.id))
                onSubmission({ ...submission, status: 'teacher_review_required' })
              })}
              loading={busy === 'reopen'}
            >
              <RotateCcw /> Reopen
            </Button>
          )}
        </div>
      </div>

      <HistoryList evaluationId={evaluation.id} refreshKey={`${evaluation.review_status}:${evaluation.final_total}:${evaluation.teacher_comment}`} />

      <Dialog
        open={rejecting}
        onOpenChange={setRejecting}
        title="Reject and re-mark?"
        description="The answers are marked again in a new run. Your changes to this run are not carried over; the reason is kept with it."
        footer={
          <>
            <Button variant="secondary" onClick={() => setRejecting(false)}>
              Cancel
            </Button>
            <Button
              variant="dangerSolid"
              disabled={reason.trim().length < 3}
              loading={busy === 'reject'}
              onClick={() => act('reject', async () => {
                onSubmission(await reviewApi.reject(evaluation.id, reason.trim()))
                setRejecting(false)
                toast.success('Sent back for re-marking')
              })}
            >
              Reject and re-mark
            </Button>
          </>
        }
      >
        <FormField label="Reason">
          <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="What was wrong with these marks?" />
        </FormField>
      </Dialog>
    </Card>
  )
}
