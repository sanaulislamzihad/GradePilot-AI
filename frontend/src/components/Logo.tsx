import { Check } from 'lucide-react'
import { cn } from '@/utils/cn'

export function Logo({ className, compact }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn('inline-flex items-center gap-2 font-semibold tracking-tight text-zinc-900', className)}>
      <span className="flex size-7 items-center justify-center rounded-md bg-zinc-900 text-white">
        <Check className="size-4" strokeWidth={3} aria-hidden />
      </span>
      {!compact && <span className="text-[15px]">GradePilot AI</span>}
    </span>
  )
}
