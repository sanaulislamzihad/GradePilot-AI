import { Link } from 'react-router'
import { buttonVariants } from '@/components/ui/Button'

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 text-center">
      <p className="font-mono text-sm text-zinc-400">404</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-900">Page not found</h1>
      <p className="mt-2 text-sm text-zinc-500">The page you are looking for does not exist or has moved.</p>
      <Link to="/" className={buttonVariants({ variant: 'secondary', className: 'mt-6' })}>
        Back to home
      </Link>
    </div>
  )
}
