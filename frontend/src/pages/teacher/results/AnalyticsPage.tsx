import { BarChart3 } from 'lucide-react'
import { Link } from 'react-router'
import { BarChart, ChartWithTable, ColumnChart } from '@/components/charts/charts'
import { DownloadButton } from '@/components/DownloadButton'
import { buttonVariants } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Select } from '@/components/ui/Input'
import { PageHeader } from '@/components/ui/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { useAsync } from '@/hooks/useAsync'
import { resultsApi } from '@/services/api'
import type { ExamAnalytics } from '@/types/api'
import { formatMarks } from '@/utils/format'
import { useExamParam } from './useExamParam'

const percent = (value: number | null) => (value === null ? '—' : `${formatMarks(value)}%`)

function Figure({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="p-5">
      <p className="text-[13px] font-medium text-zinc-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-zinc-900">{value}</p>
      {hint && <p className="mt-1 text-[13px] text-zinc-500">{hint}</p>}
    </Card>
  )
}

function Overview({ stats }: { stats: ExamAnalytics }) {
  const out = (value: number | null) => (value === null ? '—' : `${formatMarks(value)} / ${formatMarks(stats.total_marks)}`)
  const students = (n: number) => `${n} student${n === 1 ? '' : 's'}`

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Figure label="Average" value={out(stats.average)} hint={stats.average_percentage === null ? undefined : `${percent(stats.average_percentage)} of total marks`} />
        <Figure label="Median" value={out(stats.median)} />
        <Figure label="Highest" value={out(stats.highest)} hint={stats.lowest === null ? undefined : `Lowest ${out(stats.lowest)}`} />
        <Figure
          label="Graded"
          value={`${stats.graded_count} of ${stats.total_submissions}`}
          hint={`${stats.pending_evaluations} not yet approved · ${stats.published_results} published`}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title="Score distribution" description="Number of students in each percentage band." />
          <CardBody>
            <ChartWithTable
              columns={['Score', 'Students']}
              rows={stats.distribution.map((b) => [b.label, String(b.count)])}
              chart={
                <ColumnChart
                  title={`Score distribution for ${stats.exam_title}`}
                  data={stats.distribution.map((b) => ({
                    key: b.label,
                    label: b.label.replace('–', '-').split('-')[0]!,
                    value: b.count,
                    detail: `${b.label}: ${students(b.count)}`,
                  }))}
                  format={(v) => (Number.isInteger(v) ? String(v) : '')}
                />
              }
            />
            <p className="mt-1 text-xs text-zinc-500">Bands start at the label shown, e.g. 40 covers 40–50%.</p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Average score by question" description="Average marks as a percentage of each question's total." />
          <CardBody>
            <ChartWithTable
              columns={['Question', 'Average']}
              rows={stats.questions.map((q) => [`Q${q.label}`, `${formatMarks(q.average)} / ${formatMarks(q.max_marks)} (${percent(q.average_percentage)})`])}
              chart={
                <BarChart
                  title={`Average score by question for ${stats.exam_title}`}
                  max={100}
                  format={(v) => `${formatMarks(v)}%`}
                  data={stats.questions.map((q) => ({
                    key: q.label,
                    label: `Q${q.label}`,
                    value: q.average_percentage ?? 0,
                    detail: `${formatMarks(q.average)} of ${formatMarks(q.max_marks)} marks · answered by ${q.answered}`,
                  }))}
                />
              }
            />
          </CardBody>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title="Weakest questions" description="Lowest average scores, where students may need more help." />
          <ul className="divide-y divide-zinc-100">
            {stats.weakest_questions.map((q) => (
              <li key={q.label} className="flex items-start justify-between gap-4 px-5 py-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-zinc-900">Question {q.label}</p>
                  <p className="line-clamp-2 text-[13px] text-zinc-500">{q.text}</p>
                </div>
                <p className="shrink-0 text-sm text-zinc-900 tabular-nums">{percent(q.average_percentage)}</p>
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <CardHeader title="Common missing concepts" description="Ideas most often missing from approved answers, by number of students." />
          {stats.common_missing_concepts.length === 0 ? (
            <p className="px-5 py-6 text-sm text-zinc-500">No missing concepts were recorded.</p>
          ) : (
            <ul className="divide-y divide-zinc-100">
              {stats.common_missing_concepts.map((c) => (
                <li key={c.concept} className="flex items-center justify-between gap-4 px-5 py-2.5">
                  <span className="text-sm text-zinc-800">{c.concept}</span>
                  <span className="shrink-0 text-[13px] text-zinc-500 tabular-nums">{students(c.count)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}

export default function AnalyticsPage() {
  const picker = useExamParam()
  const { data, error, loading, reload } = useAsync(
    () => (picker.examId ? resultsApi.analytics(picker.examId) : Promise.resolve(null)),
    `exam-analytics:${picker.examId}`,
  )
  const exam = picker.exams.find((e) => e.id === picker.examId)
  const fileBase = (exam?.title ?? 'exam').replace(/[^\w-]+/g, '-').replace(/^-+|-+$/g, '') || 'exam'

  return (
    <>
      <PageHeader
        title="Analytics"
        description="Class performance from teacher-approved marks only. Results still under review are not counted."
        actions={
          data && (
            <>
              <Link to={`/teacher/results?exam=${data.exam_id}`} className={buttonVariants({ variant: 'secondary' })}>
                Results
              </Link>
              <DownloadButton load={() => resultsApi.classReport(data.exam_id)} filename={`${fileBase}-report.pdf`}>
                Class report
              </DownloadButton>
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
          <EmptyState icon={BarChart3} title="No data yet" description="Analytics appear once students submit and you approve their results." />
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
          ) : data && data.graded_count === 0 ? (
            <Card>
              <EmptyState
                icon={BarChart3}
                title="No approved results yet"
                description={`${data.total_submissions} submission${data.total_submissions === 1 ? '' : 's'}, none approved yet. Approve results in AI Evaluation to see statistics.`}
                action={
                  <Link to={`/teacher/evaluation?exam=${data.exam_id}`} className={buttonVariants({ variant: 'secondary', size: 'sm' })}>
                    Go to AI Evaluation
                  </Link>
                }
              />
            </Card>
          ) : data ? (
            <Overview stats={data} />
          ) : null}
        </div>
      )}
    </>
  )
}
