import { ArrowLeft } from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import { toast } from 'sonner'
import { Card, CardBody } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { examApi } from '@/services/api'
import { ExamDetailsForm } from './ExamDetailsForm'

export default function CreateExamPage() {
  const navigate = useNavigate()
  return (
    <>
      <PageHeader
        eyebrow={
          <Link to="/teacher/exams" className="inline-flex items-center gap-1 hover:text-zinc-900">
            <ArrowLeft className="size-3.5" /> My Exams
          </Link>
        }
        title="Create exam"
        description="Start with the exam details. You will add the question paper, marks, model answers and rubrics next."
      />
      <Card className="max-w-3xl">
        <CardBody className="py-6">
          <ExamDetailsForm
            submitLabel="Create draft and continue"
            onSubmit={async (payload) => {
              const exam = await examApi.create(payload)
              toast.success('Draft exam created')
              navigate(`/teacher/exams/${exam.id}/paper`, { replace: true })
            }}
          />
        </CardBody>
      </Card>
    </>
  )
}
