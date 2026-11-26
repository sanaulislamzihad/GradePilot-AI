import { UploadCloud } from 'lucide-react'
import { useId, useRef, useState, type DragEvent } from 'react'
import { Spinner } from '@/components/ui/States'
import { cn } from '@/utils/cn'

interface FileUploadProps {
  /** e.g. [".pdf", ".docx"] */
  accept: string[]
  maxBytes: number
  onFile: (file: File) => void | Promise<void>
  busy?: boolean
  disabled?: boolean
  hint?: string
}

/**
 * Drag-and-drop or browse. The checks here only save a round trip;
 * the server validates every file again.
 */
export function FileUpload({ accept, maxBytes, onFile, busy, disabled, hint }: FileUploadProps) {
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handle = (file: File | undefined) => {
    if (!file) return
    const extension = `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`
    if (!accept.includes(extension)) {
      setError(`Unsupported file type. Allowed: ${accept.join(', ')}`)
      return
    }
    if (file.size > maxBytes) {
      setError(`File is too large. The limit is ${Math.round(maxBytes / (1024 * 1024))} MB.`)
      return
    }
    setError(null)
    void onFile(file)
    if (inputRef.current) inputRef.current.value = ''
  }

  const onDrop = (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    if (!disabled && !busy) handle(event.dataTransfer.files[0])
  }

  return (
    <div>
      <label
        htmlFor={inputId}
        onDragOver={(e) => {
          e.preventDefault()
          if (!disabled) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-6 py-8 text-center transition-colors',
          dragging ? 'border-zinc-900 bg-zinc-50' : 'border-zinc-300 hover:border-zinc-400 hover:bg-zinc-50/60',
          (disabled || busy) && 'pointer-events-none opacity-60',
        )}
      >
        {busy ? <Spinner className="size-6" /> : <UploadCloud className="size-6 text-zinc-400" aria-hidden />}
        <span className="mt-3 text-sm font-medium text-zinc-900">
          {busy ? 'Uploading and reading the file…' : 'Drop a file here or click to browse'}
        </span>
        <span className="mt-1 text-xs text-zinc-500">
          {hint ?? `${accept.join(', ').toUpperCase()} · up to ${Math.round(maxBytes / (1024 * 1024))} MB`}
        </span>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept={accept.join(',')}
          className="sr-only"
          disabled={disabled || busy}
          onChange={(e) => handle(e.target.files?.[0])}
        />
      </label>
      {error && (
        <p role="alert" className="mt-2 text-[13px] text-red-700">
          {error}
        </p>
      )}
    </div>
  )
}
