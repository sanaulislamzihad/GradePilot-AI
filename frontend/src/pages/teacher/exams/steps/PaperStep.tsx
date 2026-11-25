import { ScanText } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { FileUpload } from '@/components/FileUpload'
import { Button } from '@/components/ui/Button'
import { CardBody } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/Dialog'
import { examApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import { leafQuestions, useExamWorkspace } from '../workspace'
import { DocumentCard } from './DocumentCard'
import { StepCard } from './StepCard'

const ACCEPT = ['.pdf', '.docx', '.jpg', '.jpeg', '.png']
const MAX_BYTES = 20 * 1024 * 1024

export function PaperStep() {
  const { exam, setExam, editable } = useExamWorkspace()
  const navigate = useNavigate()
  const [uploading, setUploading] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const [confirmReplace, setConfirmReplace] = useState(false)
  const [confirmRemove, setConfirmRemove] = useState(false)
  const paper = exam.documents.find((d) => d.kind === 'question_paper')

  const onFile = async (file: File) => {
    setUploading(true)
    try {
      setExam(await examApi.uploadQuestionPaper(exam.id, file))
      toast.success('Question paper uploaded')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setUploading(false)
    }
  }

  const extract = async (replace: boolean) => {
    setExtracting(true)
    try {
      const result = await examApi.extractQuestions(exam.id, replace)
      setExam(result.exam)
      const count = leafQuestions(result.exam).length
      toast.success(`Found ${count} gradable question${count === 1 ? '' : 's'}. Review them before continuing.`)
      navigate(`/teacher/exams/${exam.id}/questions`)
    } finally {
      setExtracting(false)
    }
  }

  return (
    <StepCard
      step="paper"
      title="Question paper"
      description="Upload the paper as PDF, DOCX or an image. Text is read directly from digital files; you review every extracted question."
    >
      <CardBody className="space-y-4">
        {paper && (
          <DocumentCard examId={exam.id} document={paper} onRemove={editable ? () => setConfirmRemove(true) : undefined} />
        )}

        {editable && (
          <FileUpload
            accept={ACCEPT}
            maxBytes={MAX_BYTES}
            onFile={onFile}
            busy={uploading}
            hint={paper ? 'Upload a new file to replace the current paper' : undefined}
          />
        )}

        {paper?.extraction_status === 'succeeded' && editable && (
          <div className="flex flex-col gap-3 rounded-lg border border-zinc-200 bg-zinc-50/60 p-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-zinc-700">
              Detect numbered questions, sub-questions and printed marks from the extracted text.
            </p>
            <Button
              onClick={() =>
                exam.questions.length
                  ? setConfirmReplace(true)
                  : extract(false).catch((err) => toast.error(errorMessage(err)))
              }
              loading={extracting}
            >
              <ScanText /> Extract questions
            </Button>
          </div>
        )}

        {!paper && (
          <p className="text-[13px] text-zinc-500">
            No paper yet? You can skip this step and type the questions in on the next step.
          </p>
        )}
      </CardBody>

      <ConfirmDialog
        open={confirmReplace}
        onOpenChange={setConfirmReplace}
        title="Replace the current questions?"
        description={`This exam already has ${exam.questions.length} question${exam.questions.length === 1 ? '' : 's'}. Extracting again deletes them, including their marks, model answers and rubrics.`}
        confirmLabel="Replace questions"
        destructive
        onConfirm={() => extract(true)}
      />
      <ConfirmDialog
        open={confirmRemove}
        onOpenChange={setConfirmRemove}
        title="Remove the question paper?"
        description="The uploaded file is deleted. Questions already created are kept."
        confirmLabel="Remove file"
        destructive
        onConfirm={async () => {
          if (!paper) return
          setExam(await examApi.removeDocument(exam.id, paper.id))
          toast.success('Question paper removed')
        }}
      />
    </StepCard>
  )
}
