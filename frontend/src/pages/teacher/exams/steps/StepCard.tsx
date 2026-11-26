import { ArrowRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { buttonVariants } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { steps, useExamWorkspace, type StepKey } from '../workspace'

interface StepCardProps {
  step: StepKey
  title: string
  description: ReactNode
  action?: ReactNode
  children: ReactNode
}

/** Common frame for a setup step, with a link to the next step. */
export function StepCard({ step, title, description, action, children }: StepCardProps) {
  const { exam } = useExamWorkspace()
  const index = steps.findIndex((s) => s.key === step)
  const next = steps[index + 1]

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title={title} description={description} action={action} />
        {children}
      </Card>
      {next && (
        <div className="flex justify-end">
          <Link to={`/teacher/exams/${exam.id}/${next.key}`} className={buttonVariants({ variant: 'secondary' })}>
            Next: {next.label} <ArrowRight />
          </Link>
        </div>
      )}
    </div>
  )
}
