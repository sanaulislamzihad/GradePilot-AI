import { cva, type VariantProps } from 'class-variance-authority'
import type { HTMLAttributes } from 'react'
import { cn } from '@/utils/cn'

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap',
  {
    variants: {
      variant: {
        neutral: 'bg-zinc-100 text-zinc-700',
        outline: 'border border-zinc-200 text-zinc-700',
        solid: 'bg-zinc-900 text-white',
      },
    },
    defaultVariants: { variant: 'neutral' },
  },
)

interface BadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

type Tone = 'positive' | 'negative' | 'warning' | 'muted'

const dotTone: Record<Tone, string> = {
  positive: 'bg-emerald-600',
  negative: 'bg-red-600',
  warning: 'bg-amber-500',
  muted: 'bg-zinc-400',
}

/** Status shown as neutral text with a small semantic dot — the only place colour appears. */
export function StatusBadge({ tone, children }: { tone: Tone; children: string }) {
  return (
    <Badge variant="outline">
      <span className={cn('size-1.5 rounded-full', dotTone[tone])} aria-hidden />
      {children}
    </Badge>
  )
}
