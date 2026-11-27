import { Check, Quote, X } from 'lucide-react'
import { StatusBadge } from '@/components/ui/Badge'
import { Card, CardHeader } from '@/components/ui/Card'
import type { Evaluation, EvaluationQuestion } from '@/types/api'
import { cn } from '@/utils/cn'
import { formatDateTime, formatMarks } from '@/utils/format'

const flagText: Record<string, string> = {
  missing_answer: 'No answer found',
  unreadable_answer: 'Unreadable — mark it yourself',
  invalid_ai_output: 'AI output rejected — mark it yourself',
  evidence_not_found: 'Quoted evidence not found in the answer',
  incomplete: 'Some questions need your marks',
}

function Flags({ flags }: { flags: string[] }) {
  if (!flags.length) return null
  return (
    <div className="flex flex-wrap gap-1.5">
      {flags.map((flag) => (
        <StatusBadge key={flag} tone={flag === 'missing_answer' ? 'muted' : 'warning'}>
          {flagText[flag] ?? flag}
        </StatusBadge>
      ))}
    </div>
  )
}

function QuestionResult({ question }: { question: EvaluationQuestion }) {
  return (
    <details className="group" open={question.flags.some((f) => f !== 'missing_answer')}>
      <summary className="flex cursor-pointer items-center justify-between gap-4 px-5 py-3.5 select-none hover:bg-zinc-50">
        <span className="flex min-w-0 items-center gap-3">
          <span className="font-mono text-sm font-medium text-zinc-900">{question.label}</span>
          <Flags flags={question.flags} />
        </span>
        <span className="shrink-0 text-sm font-semibold text-zinc-900 tabular-nums">
          {question.awarded === null ? '—' : formatMarks(question.awarded)} / {formatMarks(question.max_marks)}
        </span>
      </summary>
      <div className="space-y-4 border-t border-zinc-100 bg-zinc-50/40 px-5 py-4">
        {question.criteria.length > 0 && (
          <ul className="space-y-3">
            {question.criteria.map((criterion) => (
              <li key={criterion.name} className="rounded-md border border-zinc-200 bg-white px-3 py-2.5">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-medium text-zinc-900">{criterion.name}</p>
                  <p className="shrink-0 text-sm text-zinc-900 tabular-nums">
                    {formatMarks(criterion.awarded)} / {formatMarks(criterion.max_marks)}
                  </p>
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
            ))}
          </ul>
        )}
        {question.feedback && (
          <div>
            <p className="text-xs font-medium text-zinc-500">Feedback for the student</p>
            <p className="mt-0.5 text-sm text-zinc-800">{question.feedback}</p>
          </div>
        )}
        {question.answer_text && (
          <details>
            <summary className="cursor-pointer text-xs font-medium text-zinc-500 select-none">Student’s answer</summary>
            <p className="mt-1 text-sm whitespace-pre-line text-zinc-700">{question.answer_text}</p>
          </details>
        )}
      </div>
    </details>
  )
}

export function EvaluationView({ evaluation }: { evaluation: Evaluation }) {
  return (
    <Card>
      <CardHeader
        title="AI-suggested marks"
        description={`Suggestions from ${evaluation.provider}/${evaluation.model}, run ${evaluation.run_number}, ${formatDateTime(evaluation.completed_at)}. Review before anything is released.`}
        action={
          <div className="text-right">
            <p className="text-xl font-semibold text-zinc-900 tabular-nums">
              {evaluation.total_awarded === null ? '—' : formatMarks(evaluation.total_awarded)}
              <span className="text-sm font-normal text-zinc-500"> / {formatMarks(evaluation.total_max)}</span>
            </p>
          </div>
        }
      />
      {evaluation.flags.length > 0 && (
        <div className="border-b border-zinc-100 px-5 py-3">
          <Flags flags={evaluation.flags.filter((f) => f !== 'missing_answer')} />
        </div>
      )}
      <div className="divide-y divide-zinc-100">
        {evaluation.questions.map((q) => (
          <QuestionResult key={q.question_id} question={q} />
        ))}
      </div>
    </Card>
  )
}
