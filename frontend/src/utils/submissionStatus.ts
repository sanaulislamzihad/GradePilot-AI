import type { SubmissionStatus } from '@/types/api'

export const submissionStatusConfig: Record<
  SubmissionStatus,
  { label: string; tone: 'positive' | 'negative' | 'warning' | 'muted' }
> = {
  uploaded: { label: 'Received', tone: 'muted' },
  queued: { label: 'Queued', tone: 'muted' },
  extracting: { label: 'Reading script', tone: 'muted' },
  ocr_review_required: { label: 'Text review needed', tone: 'warning' },
  ready_for_evaluation: { label: 'Ready for evaluation', tone: 'muted' },
  evaluating: { label: 'Evaluating', tone: 'muted' },
  verifying: { label: 'Verifying', tone: 'muted' },
  teacher_review_required: { label: 'Teacher review', tone: 'warning' },
  approved: { label: 'Approved', tone: 'positive' },
  published: { label: 'Result published', tone: 'positive' },
  failed: { label: 'Failed', tone: 'negative' },
}

export const submissionStatusLabel = (status: SubmissionStatus) => submissionStatusConfig[status].label
