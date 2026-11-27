import { Download } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Button, type ButtonProps } from '@/components/ui/Button'
import { errorMessage } from '@/services/http'
import { saveBlob } from '@/utils/format'

interface DownloadButtonProps extends Omit<ButtonProps, 'onClick'> {
  load: () => Promise<Blob>
  filename: string
}

/** Fetches a file with the user's session and saves it; failures show as a toast. */
export function DownloadButton({ load, filename, children, variant = 'secondary', ...props }: DownloadButtonProps) {
  const [busy, setBusy] = useState(false)
  return (
    <Button
      variant={variant}
      loading={busy}
      onClick={async () => {
        setBusy(true)
        try {
          saveBlob(await load(), filename)
        } catch (err) {
          toast.error(errorMessage(err))
        } finally {
          setBusy(false)
        }
      }}
      {...props}
    >
      {!busy && <Download />}
      {children}
    </Button>
  )
}
