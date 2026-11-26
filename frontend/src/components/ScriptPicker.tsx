import { ArrowDown, ArrowUp, FileText, ImageIcon, UploadCloud, X } from 'lucide-react'
import { useId, useRef, useState, type DragEvent } from 'react'
import { Button } from '@/components/ui/Button'
import { cn } from '@/utils/cn'
import { formatBytes } from '@/utils/format'

interface ScriptPickerProps {
  files: File[]
  onChange: (files: File[]) => void
  /** Exam formats, e.g. ["jpeg", "jpg", "pdf", "png"] */
  formats: string[]
  maxFileBytes: number
  disabled?: boolean
}

const MAX_FILES = 30

/**
 * Choose one PDF, or several page images in order. These checks give quick
 * feedback only; the server validates everything again.
 */
export function ScriptPicker({ files, onChange, formats, maxFileBytes, disabled }: ScriptPickerProps) {
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const extensions = [...new Set(formats)].map((f) => `.${f}`)
  const allowsPdf = formats.includes('pdf')
  const allowsImages = formats.some((f) => f !== 'pdf')
  const isPdf = (file: File) => file.name.toLowerCase().endsWith('.pdf')

  const add = (incoming: File[]) => {
    if (!incoming.length) return
    for (const file of incoming) {
      const ext = `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`
      if (!extensions.includes(ext)) return setError(`${file.name}: not an accepted format (${extensions.join(', ')})`)
      if (file.size > maxFileBytes) return setError(`${file.name} is larger than ${formatBytes(maxFileBytes)}`)
      if (file.size === 0) return setError(`${file.name} is empty`)
    }
    const next = [...files, ...incoming]
    if (next.some(isPdf) && next.length > 1) {
      return setError('Upload one PDF for the whole script, or one image per page — not both.')
    }
    if (next.length > MAX_FILES) return setError(`Upload at most ${MAX_FILES} pages`)
    setError(null)
    onChange(next)
  }

  const move = (index: number, delta: number) => {
    const next = [...files]
    const [item] = next.splice(index, 1)
    next.splice(index + delta, 0, item!)
    onChange(next)
  }

  const onDrop = (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    if (!disabled) add(Array.from(event.dataTransfer.files))
  }

  const single = files.length === 1 && isPdf(files[0]!)
  const canAddMore = !disabled && !single

  return (
    <div className="space-y-3">
      {files.length > 0 && (
        <ol className="divide-y divide-zinc-100 rounded-lg border border-zinc-200">
          {files.map((file, index) => (
            <li key={`${file.name}-${file.size}-${index}`} className="flex items-center gap-3 px-3 py-2.5">
              {isPdf(file) ? <FileText className="size-4 shrink-0 text-zinc-500" /> : <ImageIcon className="size-4 shrink-0 text-zinc-500" />}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-zinc-900">
                  {!isPdf(file) && <span className="mr-1.5 text-zinc-400 tabular-nums">Page {index + 1}</span>}
                  {file.name}
                </p>
                <p className="text-xs text-zinc-500">{formatBytes(file.size)}</p>
              </div>
              {!disabled && files.length > 1 && (
                <>
                  <Button variant="ghost" size="icon" onClick={() => move(index, -1)} disabled={index === 0} aria-label={`Move ${file.name} up`}>
                    <ArrowUp />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => move(index, 1)} disabled={index === files.length - 1} aria-label={`Move ${file.name} down`}>
                    <ArrowDown />
                  </Button>
                </>
              )}
              {!disabled && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => {
                    setError(null)
                    onChange(files.filter((_, i) => i !== index))
                  }}
                  aria-label={`Remove ${file.name}`}
                >
                  <X />
                </Button>
              )}
            </li>
          ))}
        </ol>
      )}

      {canAddMore && (
        <label
          htmlFor={inputId}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            'flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-6 text-center transition-colors',
            files.length ? 'py-4' : 'py-10',
            dragging ? 'border-zinc-900 bg-zinc-50' : 'border-zinc-300 hover:border-zinc-400 hover:bg-zinc-50/60',
          )}
        >
          <UploadCloud className="size-6 text-zinc-400" aria-hidden />
          <span className="mt-2 text-sm font-medium text-zinc-900">
            {files.length ? 'Add more pages' : 'Drop your answer script here or click to browse'}
          </span>
          <span className="mt-1 text-xs text-zinc-500">
            {[allowsPdf && 'one PDF', allowsImages && 'or one image per page'].filter(Boolean).join(' ')} ·{' '}
            {extensions.join(', ').toUpperCase()} · up to {formatBytes(maxFileBytes)} each
          </span>
          <input
            ref={inputRef}
            id={inputId}
            type="file"
            multiple={allowsImages}
            accept={extensions.join(',')}
            className="sr-only"
            onChange={(e) => {
              add(Array.from(e.target.files ?? []))
              e.target.value = ''
            }}
          />
        </label>
      )}

      {error && (
        <p role="alert" className="text-[13px] text-red-700">
          {error}
        </p>
      )}
    </div>
  )
}
