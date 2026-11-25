import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Card } from '@/components/ui/Card'

interface StatCardProps {
  label: string
  value: number | string
  icon: LucideIcon
  hint?: ReactNode
}

export function StatCard({ label, value, icon: Icon, hint }: StatCardProps) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <p className="text-[13px] font-medium text-zinc-500">{label}</p>
        <Icon className="size-4 text-zinc-400" aria-hidden />
      </div>
      <p className="mt-3 text-2xl font-semibold tracking-tight text-zinc-900 tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-[13px] text-zinc-500">{hint}</p>}
    </Card>
  )
}
