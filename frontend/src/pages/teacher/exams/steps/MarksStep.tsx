import { Calculator } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { EmptyState } from '@/components/ui/States'
import { TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table'
import { examApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import { cn } from '@/utils/cn'
import { formatMarks, hasTwoDecimalsAtMost } from '@/utils/format'
import { leafQuestions, useExamWorkspace } from '../workspace'
import { StepCard } from './StepCard'

const round2 = (n: number) => Math.round(n * 100) / 100

export function MarksStep() {
  const { exam, setExam, editable } = useExamWorkspace()
  const leaves = useMemo(() => leafQuestions(exam), [exam])
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(leaves.map((q) => [q.id, q.marks === null ? '' : String(q.marks)])),
  )
  const [saving, setSaving] = useState(false)

  const parsed = leaves.map((q) => {
    const raw = values[q.id] ?? ''
    const value = raw.trim() === '' ? null : Number(raw)
    const invalid = value !== null && (!Number.isFinite(value) || value <= 0 || !hasTwoDecimalsAtMost(value) || value > 1000)
    return { question: q, raw, value, invalid }
  })
  const allocated = round2(parsed.reduce((sum, p) => sum + (p.invalid || p.value === null ? 0 : p.value), 0))
  const remaining = round2(exam.total_marks - allocated)
  const dirty = parsed.some((p) => (p.value ?? null) !== p.question.marks)
  const anyInvalid = parsed.some((p) => p.invalid)

  const save = async () => {
    setSaving(true)
    try {
      const updated = await examApi.saveMarks(
        exam.id,
        parsed.map((p) => ({ question_id: p.question.id, marks: p.value })),
      )
      setExam(updated)
      toast.success('Marks saved')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <StepCard
      step="marks"
      title="Marks"
      description="Assign marks to every gradable question. The total must equal the exam's total marks before it can be published."
    >
      {leaves.length === 0 ? (
        <EmptyState icon={Calculator} title="No questions yet" description="Add questions first, then allocate marks." />
      ) : (
        <>
          <Table>
            <THead>
              <tr>
                <TH className="w-20">No.</TH>
                <TH>Question</TH>
                <TH className="w-36 text-right">Marks</TH>
              </tr>
            </THead>
            <TBody>
              {parsed.map(({ question, raw, invalid }) => (
                <TR key={question.id}>
                  <TD className="font-mono text-zinc-900">{question.full_label}</TD>
                  <TD>
                    <p className="line-clamp-2 text-zinc-700">{question.text || <span className="text-zinc-400">No text</span>}</p>
                  </TD>
                  <TD className="text-right">
                    <Input
                      type="number"
                      inputMode="decimal"
                      min="0"
                      step="any"
                      value={raw}
                      onChange={(e) => setValues((v) => ({ ...v, [question.id]: e.target.value }))}
                      aria-label={`Marks for question ${question.full_label}`}
                      aria-invalid={invalid || undefined}
                      className="ml-auto h-8 w-24 text-right tabular-nums"
                      disabled={!editable}
                    />
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
          <div className="flex flex-col gap-3 border-t border-zinc-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm">
              <span className="font-medium text-zinc-900 tabular-nums">
                {formatMarks(allocated)} / {formatMarks(exam.total_marks)}
              </span>{' '}
              <span className={cn('tabular-nums', remaining === 0 ? 'text-zinc-500' : 'text-red-700')}>
                {remaining === 0
                  ? 'allocated — matches the exam total'
                  : remaining > 0
                    ? `· ${formatMarks(remaining)} still to allocate`
                    : `· ${formatMarks(-remaining)} over the exam total`}
              </span>
              {anyInvalid && <p className="mt-1 text-[13px] text-red-700">Marks must be positive numbers with at most two decimals.</p>}
            </div>
            {editable && (
              <Button onClick={save} loading={saving} disabled={!dirty || anyInvalid}>
                Save marks
              </Button>
            )}
          </div>
        </>
      )}
    </StepCard>
  )
}
