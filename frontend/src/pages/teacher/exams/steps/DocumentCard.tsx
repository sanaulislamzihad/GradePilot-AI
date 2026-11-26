import { Download, FileText, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { examApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import type { ExamDocument } from '@/types/api'
import { formatBytes, formatDateTime, saveBlob } from '@/utils/format'

const statusTone = { succeeded: 'positive', needs_ocr: 'warning', failed: 'negative' } as const
const statusLabel = { succeeded: 'Text extracted', needs_ocr: 'Needs OCR', failed: 'Could not read' } as const

interface DocumentCardProps {
  examId: string
  document: ExamDocument
  onRemove?: () => void
}

export function DocumentCard({ examId, document, onRemove }: DocumentCardProps) {
  const [downloading, setDownloading] = useState(false)

  const download = async () => {
    setDownloading(true)
    try {
      saveBlob(await examApi.downloadDocument(examId, document.id), document.original_filename)
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="rounded-lg border border-zinc-200">
      <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-md border border-zinc-200 bg-zinc-50">
            <FileText className="size-4 text-zinc-500" aria-hidden />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-zinc-900">{document.original_filename}</p>
            <p className="text-xs text-zinc-500">
              {formatBytes(document.size_bytes)}
              {document.page_count ? ` · ${document.page_count} page${document.page_count === 1 ? '' : 's'}` : ''} · uploaded{' '}
              {formatDateTime(document.created_at)}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <StatusBadge tone={statusTone[document.extraction_status]}>{statusLabel[document.extraction_status]}</StatusBadge>
          <Button variant="ghost" size="icon" onClick={download} loading={downloading} aria-label="Download file">
            {!downloading && <Download />}
          </Button>
          {onRemove && (
            <Button variant="ghost" size="icon" onClick={onRemove} aria-label="Remove file">
              <Trash2 />
            </Button>
          )}
        </div>
      </div>
      {document.extraction_message && (
        <p className="border-t border-zinc-100 px-4 py-2.5 text-[13px] text-zinc-600">{document.extraction_message}</p>
      )}
      {document.extracted_text && (
        <details className="group border-t border-zinc-100">
          <summary className="cursor-pointer px-4 py-2.5 text-[13px] font-medium text-zinc-700 select-none hover:bg-zinc-50">
            View extracted text
          </summary>
          <pre className="max-h-80 overflow-auto border-t border-zinc-100 bg-zinc-50/60 px-4 py-3 font-mono text-xs leading-relaxed whitespace-pre-wrap text-zinc-700">
            {document.extracted_text}
          </pre>
        </details>
      )}
    </div>
  )
}
