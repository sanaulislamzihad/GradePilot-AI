import { AlertTriangle, Play, RefreshCw, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'
import { SubmissionStatusBadge } from '@/components/SubmissionStatusBadge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/States'
import { processingApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import type { SubmissionDetail } from '@/types/api'
import { IN_PROGRESS_STATUSES } from '@/utils/submissionStatus'

const IN_PROGRESS = IN_PROGRESS_STATUSES

interface ProcessingPanelProps {
  submission: SubmissionDetail
  hasEvaluator: boolean
  onUpdated: (submission: SubmissionDetail) => void
}

export function ProcessingPanel({ submission, hasEvaluator, onUpdated }: ProcessingPanelProps) {
  const [busy, setBusy] = useState<string | null>(null)
  const status = submission.status
  const running = IN_PROGRESS.includes(status)

  const run = async (action: 'extract' | 'retry' | 'evaluate', label: string) => {
    setBusy(action)
    try {
      const updated = await processingApi[action](submission.id)
      onUpdated(updated)
      if (updated.status === 'failed') toast.error('Processing failed. See the reason below.')
      else toast.success(label)
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  const canProcess = status === 'uploaded'
  const canRetry = status === 'failed'
  // Re-marking a run under review goes through 'Reject and re-mark' in the review panel.
  const canRemark = status === 'ready_for_evaluation'

  return (
    <Card>
      <CardHeader
        title="AI processing"
        description="Reading the script, splitting it by question and suggesting marks. You review every result."
        action={<SubmissionStatusBadge status={status} />}
      />
      <div className="space-y-3 px-5 py-4">
        {running && (
          <p className="flex items-center gap-2 text-sm text-zinc-700" role="status">
            <Spinner className="size-4" /> {submission.status_message ?? 'Working…'} This page updates automatically.
          </p>
        )}
        {submission.processing_error && (
          <div role="alert" className="flex gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
            <span>{submission.processing_error}</span>
          </div>
        )}
        {status === 'ocr_review_required' && (
          <p className="text-sm text-zinc-700">
            Some answers were hard to read or could not be matched to a question. Check them below, correct anything
            wrong, then confirm to mark.
          </p>
        )}
        {!hasEvaluator ? (
          <p className="text-sm text-zinc-600">
            Set up an evaluator model in{' '}
            <Link to="/teacher/ai-settings" className="font-medium text-zinc-900 underline underline-offset-4">
              AI Settings
            </Link>{' '}
            to read and mark scripts.
          </p>
        ) : (
          !running && (
            <div className="flex flex-wrap gap-2">
              {canProcess && (
                <Button onClick={() => run('extract', 'Processing finished')} loading={busy === 'extract'}>
                  <Play /> Read and mark
                </Button>
              )}
              {canRetry && (
                <Button onClick={() => run('retry', 'Processing finished')} loading={busy === 'retry'}>
                  <RotateCcw /> Retry
                </Button>
              )}
              {canRemark && (
                <Button variant="secondary" onClick={() => run('evaluate', 'Marking finished')} loading={busy === 'evaluate'}>
                  <RefreshCw /> Mark again
                </Button>
              )}
              {(canRemark || canRetry || status === 'teacher_review_required') && (
                <Button variant="ghost" onClick={() => run('extract', 'Script read again')} loading={busy === 'extract'}>
                  Read script again
                </Button>
              )}
            </div>
          )
        )}
      </div>
    </Card>
  )
}
