import { Award, BarChart3, Send, Undo2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'
import { DownloadButton } from '@/components/DownloadButton'
import { SubmissionStatusBadge } from '@/components/SubmissionStatusBadge'
import { Button, buttonVariants } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/Dialog'
import { Select } from '@/components/ui/Input'
import { PageHeader } from '@/components/ui/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { TBody, TD, TH, THead, TR, Table } from '@/components/ui/Table'
import { useAsync } from '@/hooks/useAsync'
import { resultsApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import type { ExamResultRow, ExamResults, ReleaseSettings, ResultReleaseMode } from '@/types/api'
import { cn } from '@/utils/cn'
import { formatDateTime, formatMarks } from '@/utils/format'
import { useExamParam } from './useExamParam'

const MODES: { value: ResultReleaseMode; title: string; description: string }[] = [
  {
    value: 'after_approval',
    title: 'Release after teacher approval',
    description: 'Students see nothing until you approve and publish each result.',
  },
  {
    value: 'provisional',
    title: 'Show provisional marks',
    description: 'Students see AI-suggested marks, clearly labelled provisional, as soon as marking finishes. Final marks still need your approval.',
  },
]

function ReleaseSettingsCard({ examId, initial, onSaved }: { examId: string; initial: ReleaseSettings; onSaved: (s: ReleaseSettings) => void }) {
  const [settings, setSettings] = useState<ReleaseSettings>({
    result_release_mode: initial.result_release_mode,
    release_teacher_comments: initial.release_teacher_comments,
  })
  const [saving, setSaving] = useState(false)
  const dirty = settings.result_release_mode !== initial.result_release_mode || settings.release_teacher_comments !== initial.release_teacher_comments

  const save = async () => {
    setSaving(true)
    try {
      onSaved(await resultsApi.saveSettings(examId, settings))
      toast.success('Release settings saved')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="h-fit">
      <CardHeader title="Release settings" description="Applies to this exam. You can change it at any time." />
      <fieldset className="grid gap-2 px-5 pt-4 md:grid-cols-2 2xl:grid-cols-1">
        <legend className="sr-only">When students see results</legend>
        {MODES.map((mode) => (
          <label
            key={mode.value}
            className={cn(
              'flex cursor-pointer gap-3 rounded-md border p-3',
              settings.result_release_mode === mode.value ? 'border-zinc-900' : 'border-zinc-200 hover:border-zinc-300',
            )}
          >
            <input
              type="radio"
              name="release-mode"
              className="mt-0.5 accent-zinc-900"
              checked={settings.result_release_mode === mode.value}
              onChange={() => setSettings((s) => ({ ...s, result_release_mode: mode.value }))}
            />
            <span>
              <span className="block text-sm font-medium text-zinc-900">{mode.title}</span>
              <span className="mt-0.5 block text-[13px] text-zinc-500">{mode.description}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <label className="flex items-start gap-3 px-5 py-4 text-sm text-zinc-700">
        <input
          type="checkbox"
          className="mt-0.5 accent-zinc-900"
          checked={settings.release_teacher_comments}
          onChange={(e) => setSettings((s) => ({ ...s, release_teacher_comments: e.target.checked }))}
        />
        <span>
          Include my review comments in published results
          <span className="mt-0.5 block text-[13px] text-zinc-500">Comments are never shown on provisional results.</span>
        </span>
      </label>
      <div className="flex justify-end border-t border-zinc-200 px-5 py-3">
        <Button size="sm" onClick={save} loading={saving} disabled={!dirty}>
          Save settings
        </Button>
      </div>
    </Card>
  )
}

function RowAction({ row, onChanged }: { row: ExamResultRow; onChanged: () => void }) {
  const [busy, setBusy] = useState(false)
  const run = async (action: () => Promise<unknown>, message: string) => {
    setBusy(true)
    try {
      await action()
      toast.success(message)
      onChanged()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }
  if (row.published) {
    return (
      <Button size="sm" variant="ghost" loading={busy} onClick={() => run(() => resultsApi.withdraw(row.submission_id), `Result for ${row.student_name} withdrawn`)}>
        {!busy && <Undo2 />} Withdraw
      </Button>
    )
  }
  if (row.status === 'approved') {
    return (
      <Button size="sm" variant="secondary" loading={busy} onClick={() => run(() => resultsApi.publish(row.submission_id), `Result for ${row.student_name} published`)}>
        {!busy && <Send />} Publish
      </Button>
    )
  }
  return <span className="text-[13px] text-zinc-400">{row.status === 'teacher_review_required' ? 'Awaiting approval' : 'Not marked'}</span>
}

function ResultsTable({ results, onChanged }: { results: ExamResults; onChanged: () => void }) {
  if (results.rows.length === 0) {
    return <EmptyState icon={Award} title="No submissions yet" description="Results appear here once students submit and their scripts are marked." />
  }
  return (
    <Table>
      <THead>
        <tr>
          <TH>Student</TH>
          <TH>Status</TH>
          <TH className="text-right">Marks</TH>
          <TH className="hidden text-right sm:table-cell">%</TH>
          <TH className="hidden lg:table-cell">Published</TH>
          <TH className="text-right">Action</TH>
        </tr>
      </THead>
      <TBody>
        {results.rows.map((row) => (
          <TR key={row.submission_id}>
            <TD>
              {row.final_total !== null ? (
                <Link to={`/teacher/results/${row.submission_id}`} className="font-medium text-zinc-900 hover:underline">
                  {row.student_name}
                </Link>
              ) : (
                <Link to={`/teacher/submissions/${row.submission_id}`} className="font-medium text-zinc-900 hover:underline">
                  {row.student_name}
                </Link>
              )}
              <p className="font-mono text-xs whitespace-nowrap text-zinc-500">
                {row.student_number} · {row.submission_code}
              </p>
            </TD>
            <TD>
              <SubmissionStatusBadge status={row.status} />
            </TD>
            <TD className="text-right whitespace-nowrap tabular-nums">
              <span className="font-medium text-zinc-900">{formatMarks(row.final_total)}</span>
              <span className="text-zinc-500"> / {formatMarks(row.max_marks)}</span>
            </TD>
            <TD className="hidden text-right text-zinc-700 tabular-nums sm:table-cell">{row.percentage === null ? '—' : `${formatMarks(row.percentage)}%`}</TD>
            <TD className="hidden text-[13px] whitespace-nowrap text-zinc-600 lg:table-cell">{row.published ? formatDateTime(row.published_at) : '—'}</TD>
            <TD className="text-right">
              <RowAction row={row} onChanged={onChanged} />
            </TD>
          </TR>
        ))}
      </TBody>
    </Table>
  )
}

export default function ResultsPage() {
  const picker = useExamParam()
  const [confirming, setConfirming] = useState(false)
  const { data, error, loading, reload, setData } = useAsync(
    () => (picker.examId ? resultsApi.forExam(picker.examId) : Promise.resolve(null)),
    `exam-results:${picker.examId}`,
  )
  const exam = picker.exams.find((e) => e.id === picker.examId)
  const fileBase = (exam?.title ?? 'exam').replace(/[^\w-]+/g, '-').replace(/^-+|-+$/g, '') || 'exam'

  return (
    <>
      <PageHeader
        title="Results"
        description="Publish approved results to students and export marks. Only teacher-approved marks can be published."
        actions={
          data && (
            <>
              <DownloadButton load={() => resultsApi.resultsCsv(data.exam_id)} filename={`${fileBase}-results.csv`}>
                CSV
              </DownloadButton>
              <Link to={`/teacher/analytics?exam=${data.exam_id}`} className={buttonVariants({ variant: 'secondary' })}>
                <BarChart3 /> Analytics
              </Link>
              <Button onClick={() => setConfirming(true)} disabled={data.approved_unpublished === 0}>
                <Send /> Publish approved ({data.approved_unpublished})
              </Button>
            </>
          )
        }
      />

      {picker.loading ? (
        <LoadingState />
      ) : picker.error ? (
        <ErrorState message={picker.error} />
      ) : picker.exams.length === 0 ? (
        <Card>
          <EmptyState icon={Award} title="No results yet" description="Once students submit to one of your exams, its results are managed here." />
        </Card>
      ) : (
        <div className="space-y-4">
          <Select value={picker.examId} onChange={(e) => picker.select(e.target.value)} aria-label="Exam" className="sm:w-80">
            {picker.exams.map((e) => (
              <option key={e.id} value={e.id}>
                {e.title}
                {e.course_code ? ` (${e.course_code})` : ''}
              </option>
            ))}
          </Select>
          {loading && !data ? (
            <LoadingState />
          ) : error ? (
            <ErrorState message={error} onRetry={reload} />
          ) : data ? (
            <div className="grid gap-6 2xl:grid-cols-3">
              <Card className="2xl:col-span-2">
                <ResultsTable results={data} onChanged={reload} />
              </Card>
              <ReleaseSettingsCard
                key={data.exam_id}
                examId={data.exam_id}
                initial={data}
                onSaved={(settings) => setData((current) => (current ? { ...current, ...settings } : current))}
              />
            </div>
          ) : null}
        </div>
      )}

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={`Publish ${data?.approved_unpublished ?? 0} approved result${data?.approved_unpublished === 1 ? '' : 's'}?`}
        description="Students will see their final marks and feedback straight away. Results still under review are not affected. You can withdraw a published result later."
        confirmLabel="Publish"
        onConfirm={async () => {
          const result = await resultsApi.publishAll(picker.examId)
          toast.success(`${result.published} published${result.skipped ? `, ${result.skipped} not approved yet` : ''}`)
          reload()
        }}
      />
    </>
  )
}
