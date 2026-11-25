import { toast } from 'sonner'
import { CardBody } from '@/components/ui/Card'
import { examApi } from '@/services/api'
import { ExamDetailsForm } from '../ExamDetailsForm'
import { useExamWorkspace } from '../workspace'
import { StepCard } from './StepCard'

export function DetailsStep() {
  const { exam, setExam, editable } = useExamWorkspace()
  return (
    <StepCard step="details" title="Exam details" description="Basic information and the submission policy students must follow.">
      <CardBody className="py-6">
        <ExamDetailsForm
          // Re-mount after saving so the form's "unchanged" baseline is the saved exam.
          key={exam.updated_at}
          exam={exam}
          disabled={!editable}
          submitLabel="Save details"
          onSubmit={async (payload) => {
            setExam(await examApi.update(exam.id, payload))
            toast.success('Exam details saved')
          }}
        />
      </CardBody>
    </StepCard>
  )
}
