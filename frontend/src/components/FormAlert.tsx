import { AlertCircle } from 'lucide-react'

export function FormAlert({ message }: { message: string | null | undefined }) {
  if (!message) return null
  return (
    <div role="alert" className="flex gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-800">
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>{message}</span>
    </div>
  )
}
