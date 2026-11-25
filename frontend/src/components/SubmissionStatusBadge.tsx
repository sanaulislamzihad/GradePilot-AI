import { StatusBadge } from '@/components/ui/Badge'
import type { SubmissionStatus } from '@/types/api'
import { submissionStatusConfig } from '@/utils/submissionStatus'

export function SubmissionStatusBadge({ status }: { status: SubmissionStatus }) {
  const { label, tone } = submissionStatusConfig[status]
  return <StatusBadge tone={tone}>{label}</StatusBadge>
}
