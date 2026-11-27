import { ArrowLeft, Info } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { DownloadButton } from '@/components/DownloadButton'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { ErrorState, LoadingState } from '@/components/ui/States'
import { useAsync } from '@/hooks/useAsync'
import { useAuth } from '@/hooks/useAuth'
import { resultsApi } from '@/services/api'
import type { ResultQuestion, ResultView } from '@/types/api'
import { formatDate, formatMarks } from '@/utils/format'

function QuestionResult({ question }: { question: ResultQuestion }) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-4 border-b border-zinc-200 px-5 py-4">
        <div className="min-w-0">
          <h3 className="text-[15px] font-semibold text-zinc-900">Question {question.label}</h3>
          <p className="mt-0.5 text-sm whitespace-pre-line text-zinc-500">{question.text}</p>
        </div>
        <p className="shrink-0 text-sm text-zinc-500 tabular-nums">
          <span className="text-base font-semibold text-zinc-900">{formatMarks(question.awarded)}</span> / {formatMarks(question.max_marks)}
        </p>
      </div>
      <div className="space-y-4 px-5 py-4 text-sm">
        {!question.answered && <p className="text-zinc-500">No answer was found for this question.</p>}
        {question.criteria.length > 0 && (
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-xs text-zinc-500">
                <th className="pb-2 font-medium">Criterion</th>
                <th className="pb-2 text-right font-medium">Marks</th>
              </tr>
            </thead>
            <tbody>
              {question.criteria.map((c) => (
                <tr key={c.name} className="border-b border-zinc-100 align-top last:border-0">
                  <td className="py-2 pr-4">
                    <p className="text-zinc-900">{c.name}</p>
                    {c.explanation && <p className="mt-0.5 text-[13px] text-zinc-500">{c.explanation}</p>}
                  </td>
                  <td className="py-2 text-right whitespace-nowrap text-zinc-700 tabular-nums">
                    {formatMarks(c.awarded)} / {formatMarks(c.max_marks)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {question.feedback && (
          <div>
            <p className="text-xs font-medium text-zinc-500">Feedback</p>
            <p className="mt-0.5 text-zinc-800">{question.feedback}</p>
          </div>
        )}
        {question.missing_concepts.length > 0 && (
          <div>
            <p className="text-xs font-medium text-zinc-500">To improve, cover</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-zinc-800">
              {question.missing_concepts.map((concept) => (
                <li key={concept}>{concept}</li>
              ))}
            </ul>
          </div>
        )}
        {question.teacher_comment && (
          <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
            <p className="text-xs font-medium text-zinc-500">Teacher's comment</p>
            <p className="mt-0.5 text-zinc-800">{question.teacher_comment}</p>
          </div>
        )}
      </div>
    </Card>
  )
}

export function ResultSummary({ result }: { result: ResultView }) {
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[13px] font-medium text-zinc-500">Total</p>
          <p className="mt-1 text-5xl font-semibold tracking-tight text-zinc-900">
            {formatMarks(result.total)}
            <span className="text-2xl font-medium text-zinc-400"> / {formatMarks(result.max_marks)}</span>
          </p>
        </div>
        <div className="sm:text-right">
          <p className="text-2xl font-semibold text-zinc-900">{formatMarks(result.percentage)}%</p>
          <p className="text-[13px] text-zinc-500">{result.provisional ? 'Provisional' : `Published ${formatDate(result.published_at)}`}</p>
        </div>
      </div>
      {result.provisional && (
        <p className="mt-4 flex gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[13px] text-amber-900">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
          These marks were suggested automatically and have not been confirmed by your teacher yet. They may change.
        </p>
      )}
      {result.teacher_comment && (
        <div className="mt-4 border-t border-zinc-200 pt-4">
          <p className="text-xs font-medium text-zinc-500">Teacher's comment</p>
          <p className="mt-0.5 text-sm whitespace-pre-line text-zinc-800">{result.teacher_comment}</p>
        </div>
      )}
    </Card>
  )
}

/** A result as the student sees it. Teachers open the same page to preview what was released. */
export default function ResultDetailPage() {
  const { submissionId = '' } = useParams()
  const { user } = useAuth()
  const isTeacher = user?.role === 'teacher'
  const { data, error, loading, reload } = useAsync(() => resultsApi.get(submissionId), `result:${submissionId}`)

  if (loading && !data) return <LoadingState />
  if (error || !data) return <ErrorState message={error ?? 'Result not found'} onRetry={reload} />

  const back = isTeacher
    ? { to: `/teacher/results?exam=${data.exam_id}`, label: 'Results' }
    : { to: '/student/results', label: 'My Results' }
  const course = [data.course_code, data.section_name && `Section ${data.section_name}`].filter(Boolean).join(' · ')

  return (
    <>
      <PageHeader
        eyebrow={
          <Link to={back.to} className="inline-flex items-center gap-1 hover:text-zinc-900">
            <ArrowLeft className="size-3.5" /> {back.label}
          </Link>
        }
        title={data.exam_title}
        description={
          <span className="inline-flex flex-wrap items-center gap-2">
            {data.provisional ? <Badge variant="outline">Provisional</Badge> : <Badge variant="solid">Final</Badge>}
            {course && <span>{course} ·</span>}
            <span>
              {data.student_name} · <span className="font-mono">{data.student_number}</span>
            </span>
          </span>
        }
        actions={
          <>
            {isTeacher && (
              <Link to={`/teacher/submissions/${data.submission_id}`} className="text-sm font-medium text-zinc-600 hover:text-zinc-900">
                Open review
              </Link>
            )}
            <DownloadButton load={() => resultsApi.resultPdf(data.submission_id)} filename={`${data.submission_code}-result.pdf`}>
              Download PDF
            </DownloadButton>
          </>
        }
      />
      {isTeacher && (
        <p className="mb-4 text-[13px] text-zinc-500">
          {data.provisional ? 'Preview of the current marks. Students only see this if the exam shows provisional marks.' : 'This is exactly what the student sees.'}
        </p>
      )}
      <div className="space-y-4">
        <ResultSummary result={data} />
        {data.questions.map((q) => (
          <QuestionResult key={q.label} question={q} />
        ))}
      </div>
    </>
  )
}
