import { Download, Eye, FileText, ImageIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Spinner } from '@/components/ui/States'
import { submissionApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import type { SubmissionDetail, SubmissionFile } from '@/types/api'
import { formatBytes, saveBlob } from '@/utils/format'

function filename(submission: SubmissionDetail, file: SubmissionFile) {
  const ext = file.original_filename.split('.').pop() ?? 'bin'
  return `${submission.code}-${file.position}.${ext}`
}

function Preview({ submission, file, onClose }: { submission: SubmissionDetail; file: SubmissionFile; onClose: () => void }) {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let objectUrl: string | null = null
    let active = true
    submissionApi
      .downloadFile(submission.id, file.id)
      .then((blob) => {
        if (!active) return
        objectUrl = URL.createObjectURL(new Blob([blob], { type: file.content_type }))
        setUrl(objectUrl)
      })
      .catch((err) => active && setError(errorMessage(err)))
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [submission.id, file.id, file.content_type])

  return (
    <Dialog wide open onOpenChange={(open) => !open && onClose()} title={file.original_filename} description={`${submission.code} · file ${file.position} of ${submission.file_count}`}>
      <div className="-mx-5 flex h-[70vh] items-center justify-center border-t border-zinc-200 bg-zinc-50">
        {error ? (
          <p className="text-sm text-red-700">{error}</p>
        ) : !url ? (
          <Spinner />
        ) : file.content_type === 'application/pdf' ? (
          // The blob comes from our own authorised endpoint; browsers refuse to run their PDF viewer in a sandboxed frame.
          <iframe src={url} title={file.original_filename} className="h-full w-full" />
        ) : (
          <img src={url} alt={`Page ${file.position} of the answer script`} className="max-h-full max-w-full object-contain" />
        )}
      </div>
    </Dialog>
  )
}

export function SubmissionFiles({ submission }: { submission: SubmissionDetail }) {
  const [preview, setPreview] = useState<SubmissionFile | null>(null)
  const [downloading, setDownloading] = useState<string | null>(null)

  const download = async (file: SubmissionFile) => {
    setDownloading(file.id)
    try {
      saveBlob(await submissionApi.downloadFile(submission.id, file.id), filename(submission, file))
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setDownloading(null)
    }
  }

  return (
    <>
      <ul className="divide-y divide-zinc-100">
        {submission.files.map((file) => (
          <li key={file.id} className="flex items-center gap-3 px-5 py-3">
            {file.content_type === 'application/pdf' ? (
              <FileText className="size-4 shrink-0 text-zinc-500" aria-hidden />
            ) : (
              <ImageIcon className="size-4 shrink-0 text-zinc-500" aria-hidden />
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm text-zinc-900">{file.original_filename}</p>
              <p className="text-xs text-zinc-500">
                {formatBytes(file.size_bytes)} · {file.page_count} page{file.page_count === 1 ? '' : 's'}
              </p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setPreview(file)}>
              <Eye /> View
            </Button>
            <Button variant="ghost" size="icon" onClick={() => download(file)} loading={downloading === file.id} aria-label={`Download ${file.original_filename}`}>
              {downloading !== file.id && <Download />}
            </Button>
          </li>
        ))}
      </ul>
      {preview && <Preview submission={submission} file={preview} onClose={() => setPreview(null)} />}
    </>
  )
}
