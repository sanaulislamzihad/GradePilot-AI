import * as RadixDialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Button } from '@/components/ui/Button'
import { errorMessage } from '@/services/http'

interface DialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: ReactNode
  children?: ReactNode
  footer?: ReactNode
  /** Wide layout for previews. */
  wide?: boolean
}

export function Dialog({ open, onOpenChange, title, description, children, footer, wide }: DialogProps) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-50 bg-zinc-950/40" />
        <RadixDialog.Content
          className={`fixed top-1/2 left-1/2 z-50 w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 rounded-lg border border-zinc-200 bg-white shadow-lg focus:outline-none ${wide ? 'max-w-4xl' : 'max-w-md'}`}
        >
          <div className="flex items-start justify-between gap-4 px-5 pt-5">
            <div>
              <RadixDialog.Title className="text-base font-semibold text-zinc-900">{title}</RadixDialog.Title>
              {description ? (
                <RadixDialog.Description className="mt-1 text-sm text-zinc-500">{description}</RadixDialog.Description>
              ) : (
                <RadixDialog.Description className="sr-only">{title}</RadixDialog.Description>
              )}
            </div>
            <RadixDialog.Close className="rounded-md p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700" aria-label="Close">
              <X className="size-4" />
            </RadixDialog.Close>
          </div>
          {children && <div className="px-5 pt-4">{children}</div>}
          {footer && <div className="mt-5 flex justify-end gap-2 border-t border-zinc-200 px-5 py-3">{footer}</div>}
          {!footer && <div className="pb-5" />}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  )
}

interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: ReactNode
  confirmLabel: string
  destructive?: boolean
  onConfirm: () => Promise<unknown>
}

/** Confirmation that keeps itself open, with the error inline, if the action fails. */
export function ConfirmDialog({ open, onOpenChange, title, description, confirmLabel, destructive, onConfirm }: ConfirmDialogProps) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleOpenChange = (next: boolean) => {
    if (busy) return
    if (!next) setError(null)
    onOpenChange(next)
  }

  const confirm = async () => {
    setBusy(true)
    setError(null)
    try {
      await onConfirm()
      onOpenChange(false)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={handleOpenChange}
      title={title}
      description={description}
      footer={
        <>
          <Button variant="secondary" onClick={() => handleOpenChange(false)} disabled={busy}>
            Cancel
          </Button>
          <Button variant={destructive ? 'dangerSolid' : 'primary'} onClick={confirm} loading={busy}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      {error && (
        <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </p>
      )}
    </Dialog>
  )
}
