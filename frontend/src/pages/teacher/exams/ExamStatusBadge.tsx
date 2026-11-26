import { StatusBadge } from '@/components/ui/Badge'
import type { ExamStatus } from '@/types/api'

export function ExamStatusBadge({ status }: { status: ExamStatus }) {
  return status === 'published' ? (
    <StatusBadge tone="positive">Published</StatusBadge>
  ) : (
    <StatusBadge tone="muted">Draft</StatusBadge>
  )
}
