import { ArrowRight, ClipboardCheck, FileText, ListChecks, ScanText, ShieldCheck, UserCheck } from 'lucide-react'
import { Link } from 'react-router'
import { Logo } from '@/components/Logo'
import { buttonVariants } from '@/components/ui/Button'
import { useAuth } from '@/hooks/useAuth'
import { homePath } from '@/layouts/navigation'

const workflow = [
  {
    icon: FileText,
    title: 'Set up the exam',
    body: 'Upload the question paper, confirm the extracted questions and assign marks to each one.',
  },
  {
    icon: ListChecks,
    title: 'Approve the rubric',
    body: 'Start from a model answer and a suggested rubric. Every criterion and mark is yours to edit.',
  },
  {
    icon: ScanText,
    title: 'Collect scripts',
    body: 'Students submit handwritten or typed scripts through a link or their dashboard.',
  },
  {
    icon: ClipboardCheck,
    title: 'Review and publish',
    body: 'Check suggested marks against the evidence, adjust what needs adjusting, then release results.',
  },
]

const principles = [
  {
    icon: UserCheck,
    title: 'Teachers have the final say',
    body: 'AI marks are suggestions. Nothing reaches a student until a teacher approves it, unless provisional results are switched on.',
  },
  {
    icon: ListChecks,
    title: 'Evidence for every mark',
    body: 'Each criterion score points to the part of the answer that earned it and names what was missing.',
  },
  {
    icon: ShieldCheck,
    title: 'Private by design',
    body: 'Scripts are stored privately, access is role-checked on every request and API keys never reach the browser.',
  },
]

export default function LandingPage() {
  const { user } = useAuth()

  return (
    <div className="min-h-screen bg-white">
      <header className="border-b border-zinc-200">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Logo />
          <nav className="flex items-center gap-2">
            {user ? (
              <Link to={homePath[user.role]} className={buttonVariants({ size: 'sm' })}>
                Open dashboard
              </Link>
            ) : (
              <>
                <Link to="/login" className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
                  Sign in
                </Link>
                <Link to="/register" className={buttonVariants({ size: 'sm' })}>
                  Get started
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <main>
        <section className="mx-auto max-w-6xl px-4 pt-20 pb-16 sm:px-6 sm:pt-28">
          <p className="text-sm font-medium text-zinc-500">Intelligent examination script evaluation</p>
          <h1 className="mt-4 max-w-3xl text-4xl leading-[1.1] font-semibold tracking-tight text-zinc-900 sm:text-6xl">
            Smarter checking. Fairer grading. Faster feedback.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-zinc-600">
            GradePilot AI reads answer scripts, marks them against the rubric you approve and explains every mark —
            so you spend your time reviewing judgement calls, not adding up numbers.
          </p>
          <div className="mt-10 flex flex-wrap gap-3">
            <Link to={user ? homePath[user.role] : '/register'} className={buttonVariants({ size: 'lg' })}>
              {user ? 'Open dashboard' : 'Create a free account'}
              <ArrowRight />
            </Link>
            {!user && (
              <Link to="/login" className={buttonVariants({ variant: 'secondary', size: 'lg' })}>
                Sign in
              </Link>
            )}
          </div>
        </section>

        <section className="border-t border-zinc-200 bg-zinc-50/70">
          <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
            <h2 className="text-2xl font-semibold tracking-tight text-zinc-900">How it works</h2>
            <p className="mt-2 max-w-xl text-zinc-600">Four steps from question paper to published results.</p>
            <ol className="mt-12 grid gap-px overflow-hidden rounded-lg border border-zinc-200 bg-zinc-200 sm:grid-cols-2 lg:grid-cols-4">
              {workflow.map(({ icon: Icon, title, body }, index) => (
                <li key={title} className="bg-white p-6">
                  <div className="flex items-center justify-between">
                    <Icon className="size-5 text-zinc-900" aria-hidden />
                    <span className="font-mono text-xs text-zinc-400">0{index + 1}</span>
                  </div>
                  <h3 className="mt-6 font-semibold text-zinc-900">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-zinc-600">{body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <h2 className="text-2xl font-semibold tracking-tight text-zinc-900">Built around the teacher</h2>
          <div className="mt-12 grid gap-10 md:grid-cols-3">
            {principles.map(({ icon: Icon, title, body }) => (
              <div key={title}>
                <div className="flex size-10 items-center justify-center rounded-lg border border-zinc-200">
                  <Icon className="size-5 text-zinc-900" aria-hidden />
                </div>
                <h3 className="mt-5 font-semibold text-zinc-900">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-600">{body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-zinc-950">
          <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-6 px-4 py-16 sm:flex-row sm:items-center sm:px-6">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight text-white">Ready to set up your first course?</h2>
              <p className="mt-2 text-zinc-400">Teachers and students can register in under a minute.</p>
            </div>
            <Link
              to={user ? homePath[user.role] : '/register'}
              className={buttonVariants({ variant: 'secondary', size: 'lg', className: 'border-white' })}
            >
              {user ? 'Open dashboard' : 'Get started'}
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-zinc-200">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-8 text-sm text-zinc-500 sm:flex-row sm:justify-between sm:px-6">
          <Logo className="text-zinc-700" />
          <p>AI-suggested marks are always subject to teacher review.</p>
        </div>
      </footer>
    </div>
  )
}
