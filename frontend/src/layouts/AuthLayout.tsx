import { Check } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { Logo } from '@/components/Logo'

const points = [
  'Rubric-based marking with evidence for every criterion',
  'Teachers review, adjust and approve every result',
  'Question-wise feedback students can learn from',
]

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle: ReactNode; children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_1.1fr]">
      <aside className="hidden flex-col justify-between bg-zinc-950 p-10 text-zinc-300 lg:flex">
        <Link to="/" className="inline-flex items-center gap-2 font-semibold text-white">
          <span className="flex size-7 items-center justify-center rounded-md bg-white text-zinc-950">
            <Check className="size-4" strokeWidth={3} aria-hidden />
          </span>
          GradePilot AI
        </Link>
        <div>
          <p className="max-w-md text-3xl leading-tight font-semibold tracking-tight text-white">
            Smarter checking. Fairer grading. Faster feedback.
          </p>
          <ul className="mt-8 space-y-3">
            {points.map((point) => (
              <li key={point} className="flex gap-3 text-sm">
                <span className="mt-2 size-1 shrink-0 rounded-full bg-zinc-500" aria-hidden />
                {point}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-zinc-500">AI suggests marks. Teachers decide them.</p>
      </aside>

      <main className="flex items-center justify-center px-4 py-12 sm:px-8">
        <div className="w-full max-w-sm">
          <Link to="/" className="mb-10 inline-block lg:hidden">
            <Logo />
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">{title}</h1>
          <p className="mt-1.5 text-sm text-zinc-500">{subtitle}</p>
          <div className="mt-8">{children}</div>
        </div>
      </main>
    </div>
  )
}
