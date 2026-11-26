import { Check, Copy, Download, ExternalLink, Rocket, X } from 'lucide-react'
import QRCode from 'qrcode'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'
import { Button, buttonVariants } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { examApi } from '@/services/api'
import type { ExamDetail } from '@/types/api'
import { cn } from '@/utils/cn'
import { examTypeLabel, formatDate, formatDateTime, formatMarks, questionTypeLabel } from '@/utils/format'
import { useExamWorkspace } from '../workspace'

const checkStep: Record<string, string> = {
  details: 'details',
  questions: 'questions',
  marks: 'marks',
  model_answers: 'answers',
  rubrics: 'rubrics',
}

function ShareLink({ exam }: { exam: ExamDetail }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [copied, setCopied] = useState(false)
  const url = `${window.location.origin}/exam/${exam.public_slug}`

  useEffect(() => {
    if (canvasRef.current) {
      void QRCode.toCanvas(canvasRef.current, url, { width: 176, margin: 1, color: { dark: '#18181b', light: '#ffffff' } })
    }
  }, [url])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error('Could not copy. Select the link and copy it manually.')
    }
  }

  const downloadQr = async () => {
    const dataUrl = await QRCode.toDataURL(url, { width: 1024, margin: 2 })
    const link = document.createElement('a')
    link.href = dataUrl
    link.download = `${exam.title.replace(/[^\w\- ]+/g, '').trim() || 'exam'}-qr.png`
    link.click()
  }

  return (
    <Card>
      <CardHeader title="Share with students" description="Anyone with the link sees the exam details. Questions, answers and rubrics are never shown." />
      <CardBody className="flex flex-col gap-6 sm:flex-row">
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex gap-2">
            <Input value={url} readOnly aria-label="Exam link" className="font-mono text-[13px]" onFocus={(e) => e.target.select()} />
            <Button variant="secondary" size="icon" onClick={copy} aria-label="Copy link">
              {copied ? <Check /> : <Copy />}
            </Button>
          </div>
          <a href={url} target="_blank" rel="noreferrer" className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
            Open student view <ExternalLink />
          </a>
        </div>
        <div className="flex flex-col items-center gap-2">
          <canvas ref={canvasRef} className="rounded-md border border-zinc-200" aria-label="QR code for the exam link" role="img" />
          <Button variant="secondary" size="sm" onClick={downloadQr}>
            <Download /> Download QR
          </Button>
        </div>
      </CardBody>
    </Card>
  )
}

function PaperPreview({ exam }: { exam: ExamDetail }) {
  return (
    <Card>
      <CardHeader title="Preview" description="The exam as configured. Only you can see the questions here." />
      <CardBody className="space-y-5">
        <div>
          <h3 className="text-lg font-semibold text-zinc-900">{exam.title}</h3>
          <p className="mt-1 text-sm text-zinc-500">
            {examTypeLabel[exam.exam_type]}
            {exam.course_code && ` · ${exam.course_code}${exam.section_name ? ` Section ${exam.section_name}` : ''}`}
            {` · ${formatMarks(exam.total_marks)} marks`}
            {exam.exam_date && ` · ${formatDate(exam.exam_date)}`}
          </p>
          <p className="mt-1 text-sm text-zinc-500">Deadline: {formatDateTime(exam.submission_deadline)}</p>
          {exam.instructions && <p className="mt-3 text-sm whitespace-pre-line text-zinc-700">{exam.instructions}</p>}
        </div>
        <ol className="space-y-4 border-t border-zinc-200 pt-4">
          {exam.questions.map((q) => (
            <li key={q.id} className="text-sm">
              <div className="flex gap-3">
                <span className="w-8 shrink-0 font-mono font-medium text-zinc-900">{q.label}.</span>
                <div className="min-w-0 flex-1">
                  <div className="flex justify-between gap-4">
                    <p className="whitespace-pre-line text-zinc-800">{q.text}</p>
                    <span className="shrink-0 text-zinc-500 tabular-nums">[{formatMarks(q.marks)}]</span>
                  </div>
                  {!q.children.length && <p className="mt-0.5 text-xs text-zinc-400">{questionTypeLabel[q.question_type]}</p>}
                  {q.children.length > 0 && (
                    <ol className="mt-2 space-y-2">
                      {q.children.map((c) => (
                        <li key={c.id} className="flex gap-3">
                          <span className="w-8 shrink-0 font-mono text-zinc-700">({c.label})</span>
                          <p className="min-w-0 flex-1 whitespace-pre-line text-zinc-800">{c.text}</p>
                          <span className="shrink-0 text-zinc-500 tabular-nums">[{formatMarks(c.marks)}]</span>
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ol>
      </CardBody>
    </Card>
  )
}

export function PublishStep() {
  const { exam, setExam, editable } = useExamWorkspace()
  const [confirming, setConfirming] = useState(false)
  const { readiness } = exam

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title={exam.status === 'published' ? 'Published' : 'Ready to publish?'}
          description={
            exam.status === 'published'
              ? `Published ${formatDateTime(exam.published_at)}. The exam is locked while published.`
              : 'Every check must pass. Publishing locks the exam and creates its shareable link.'
          }
          action={
            editable && (
              <Button onClick={() => setConfirming(true)} disabled={!readiness.ready}>
                <Rocket /> Publish exam
              </Button>
            )
          }
        />
        <ul className="divide-y divide-zinc-100">
          {readiness.checks.map((check) => (
            <li key={check.key} className="flex items-center justify-between gap-4 px-5 py-3">
              <div className="flex min-w-0 items-center gap-3">
                <span
                  className={cn(
                    'flex size-5 shrink-0 items-center justify-center rounded-full',
                    check.ok ? 'bg-zinc-900 text-white' : 'border border-red-300 text-red-700',
                  )}
                  aria-hidden
                >
                  {check.ok ? <Check className="size-3" strokeWidth={3} /> : <X className="size-3" strokeWidth={3} />}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-zinc-900">
                    {check.label}
                    <span className="sr-only">{check.ok ? ' — complete' : ' — needs attention'}</span>
                  </p>
                  <p className={cn('text-[13px]', check.ok ? 'text-zinc-500' : 'text-red-700')}>{check.detail}</p>
                </div>
              </div>
              {!check.ok && editable && (
                <Link to={`/teacher/exams/${exam.id}/${checkStep[check.key]}`} className="shrink-0 text-sm font-medium text-zinc-700 underline underline-offset-4 hover:text-zinc-900">
                  Fix
                </Link>
              )}
            </li>
          ))}
        </ul>
      </Card>

      {exam.status === 'published' && exam.public_slug && <ShareLink exam={exam} />}
      {exam.status === 'published' && (
        <Card>
          <CardBody className="flex items-center justify-between gap-4">
            <p className="text-sm text-zinc-700">
              <span className="font-semibold text-zinc-900 tabular-nums">{exam.submission_count}</span> student
              {exam.submission_count === 1 ? ' has' : 's have'} submitted.
              {exam.submission_count > 0 && ' The exam can no longer be unpublished.'}
            </p>
            <Link to={`/teacher/submissions?exam=${exam.id}`} className={buttonVariants({ variant: 'secondary', size: 'sm' })}>
              View submissions
            </Link>
          </CardBody>
        </Card>
      )}
      {exam.questions.length > 0 && <PaperPreview exam={exam} />}

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Publish this exam?"
        description="Students will be able to open the exam link. Questions, marks, model answers and rubrics are locked until you unpublish."
        confirmLabel="Publish"
        onConfirm={async () => {
          setExam(await examApi.publish(exam.id))
          toast.success('Exam published')
        }}
      />
    </div>
  )
}
