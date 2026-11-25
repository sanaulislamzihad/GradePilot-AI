import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from 'react'
import { cn } from '@/utils/cn'

interface FormFieldProps {
  label: string
  error?: string
  hint?: ReactNode
  optional?: boolean
  className?: string
  /** A single input element; it receives id, aria-invalid and aria-describedby. */
  children: ReactElement<Record<string, unknown>>
}

export function FormField({ label, error, hint, optional, className, children }: FormFieldProps) {
  const id = useId()
  const messageId = `${id}-message`
  const control = isValidElement(children)
    ? cloneElement(children, {
        id,
        'aria-invalid': error ? true : undefined,
        'aria-describedby': error || hint ? messageId : undefined,
      })
    : children

  return (
    <div className={cn('space-y-1.5', className)}>
      <label htmlFor={id} className="flex items-baseline justify-between text-sm font-medium text-zinc-800">
        {label}
        {optional && <span className="text-xs font-normal text-zinc-400">Optional</span>}
      </label>
      {control}
      {error ? (
        <p id={messageId} role="alert" className="text-[13px] text-red-700">
          {error}
        </p>
      ) : hint ? (
        <p id={messageId} className="text-[13px] text-zinc-500">
          {hint}
        </p>
      ) : null}
    </div>
  )
}
