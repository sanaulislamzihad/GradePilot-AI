import { ArrowDown, ArrowUp, ListPlus, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { CardBody } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/Dialog'
import { Input, Select, Textarea } from '@/components/ui/Input'
import { EmptyState } from '@/components/ui/States'
import { examApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import type { Question, QuestionType } from '@/types/api'
import { cn } from '@/utils/cn'
import { formatMarks, questionTypeLabel } from '@/utils/format'
import { useExamWorkspace } from '../workspace'
import { StepCard } from './StepCard'

interface EditorProps {
  question: Question
  siblings: Question[]
  index: number
  nested?: boolean
  onAddSub?: () => void
  onDelete: () => void
}

function QuestionEditor({ question, siblings, index, nested, onAddSub, onDelete }: EditorProps) {
  const { exam, setExam, editable } = useExamWorkspace()
  const [label, setLabel] = useState(question.label)
  const [text, setText] = useState(question.text)
  const [type, setType] = useState<QuestionType>(question.question_type)
  const [saving, setSaving] = useState(false)
  const dirty = label !== question.label || text !== question.text || type !== question.question_type

  const save = async () => {
    if (!label.trim()) {
      toast.error('A question needs a label')
      return
    }
    setSaving(true)
    try {
      setExam(await examApi.updateQuestion(question.id, { label: label.trim(), text, question_type: type }))
      toast.success(`Question ${question.full_label} saved`)
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const move = async (delta: number) => {
    const order = siblings.map((s) => s.id)
    const [moved] = order.splice(index, 1)
    order.splice(index + delta, 0, moved!)
    try {
      setExam(await examApi.reorder(exam.id, question.parent_id, order))
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <div className={cn('space-y-2', nested && 'border-l-2 border-zinc-200 pl-4')}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-zinc-500">{nested ? 'Part' : 'Question'}</span>
        <Input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          aria-label="Question label"
          className="h-8 w-16 text-center font-mono"
          maxLength={20}
          disabled={!editable}
        />
        <Select
          value={type}
          onChange={(e) => setType(e.target.value as QuestionType)}
          aria-label="Question type"
          className="h-8 w-auto text-[13px]"
          disabled={!editable}
        >
          {Object.entries(questionTypeLabel).map(([value, text]) => (
            <option key={value} value={value}>
              {text}
            </option>
          ))}
        </Select>
        <Badge variant="outline" className="tabular-nums">
          {question.marks === null ? 'No marks' : `${formatMarks(question.marks)} marks`}
        </Badge>
        {editable && (
          <div className="ml-auto flex items-center">
            <Button variant="ghost" size="icon" onClick={() => move(-1)} disabled={index === 0} aria-label="Move up">
              <ArrowUp />
            </Button>
            <Button variant="ghost" size="icon" onClick={() => move(1)} disabled={index === siblings.length - 1} aria-label="Move down">
              <ArrowDown />
            </Button>
            {onAddSub && (
              <Button variant="ghost" size="icon" onClick={onAddSub} aria-label={`Add a part to question ${question.label}`} title="Add sub-question">
                <ListPlus />
              </Button>
            )}
            <Button variant="ghost" size="icon" onClick={onDelete} aria-label={`Delete question ${question.full_label}`}>
              <Trash2 />
            </Button>
          </div>
        )}
      </div>
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={question.children.length ? 2 : 3}
        placeholder={question.children.length ? 'Common text for all parts (optional)' : 'Question text'}
        aria-label={`Text of question ${question.full_label}`}
        disabled={!editable}
      />
      {dirty && editable && (
        <div className="flex justify-end gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setLabel(question.label)
              setText(question.text)
              setType(question.question_type)
            }}
          >
            Discard
          </Button>
          <Button size="sm" onClick={save} loading={saving}>
            Save
          </Button>
        </div>
      )}
    </div>
  )
}

export function QuestionsStep() {
  const { exam, setExam, editable } = useExamWorkspace()
  const [adding, setAdding] = useState(false)
  const [deleting, setDeleting] = useState<Question | null>(null)
  const [subFor, setSubFor] = useState<Question | null>(null)

  const addQuestion = async (parent?: Question) => {
    setAdding(true)
    try {
      setExam(await examApi.addQuestion(exam.id, { parent_id: parent?.id ?? null, text: '' }))
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setAdding(false)
    }
  }

  // Turning a gradable question into a parent drops its own marks, answer and rubric.
  const requestSub = (question: Question) => {
    if (!question.children.length && (question.marks !== null || question.model_answer || question.rubric)) {
      setSubFor(question)
    } else {
      void addQuestion(question)
    }
  }

  const leafCount = exam.questions.reduce((n, q) => n + (q.children.length || 1), 0)

  return (
    <StepCard
      step="questions"
      title="Questions"
      description={`Check every question against the paper. ${leafCount} gradable question${leafCount === 1 ? '' : 's'}; marks are set per sub-question when a question has parts.`}
      action={
        editable &&
        exam.questions.length > 0 && (
          <Button variant="secondary" size="sm" onClick={() => addQuestion()} loading={adding}>
            <Plus /> Add question
          </Button>
        )
      }
    >
      {exam.questions.length === 0 ? (
        <EmptyState
          icon={ListPlus}
          title="No questions yet"
          description="Extract them from the question paper or add them one by one."
          action={
            editable && (
              <Button variant="secondary" size="sm" onClick={() => addQuestion()} loading={adding}>
                <Plus /> Add first question
              </Button>
            )
          }
        />
      ) : (
        <CardBody className="divide-y divide-zinc-100 p-0">
          {exam.questions.map((question, index) => (
            <div key={question.id} className="space-y-4 px-5 py-5">
              <QuestionEditor
                key={`${question.id}:${question.label}:${question.text}:${question.question_type}`}
                question={question}
                siblings={exam.questions}
                index={index}
                onAddSub={() => requestSub(question)}
                onDelete={() => setDeleting(question)}
              />
              {question.children.map((child, childIndex) => (
                <QuestionEditor
                  key={`${child.id}:${child.label}:${child.text}:${child.question_type}`}
                  question={child}
                  siblings={question.children}
                  index={childIndex}
                  nested
                  onDelete={() => setDeleting(child)}
                />
              ))}
            </div>
          ))}
        </CardBody>
      )}

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={deleting ? `Delete question ${deleting.full_label}?` : ''}
        description={
          deleting?.children.length
            ? 'Its sub-questions, model answers and rubrics are deleted too.'
            : 'Its marks, model answer and rubric are deleted too.'
        }
        confirmLabel="Delete question"
        destructive
        onConfirm={async () => {
          if (!deleting) return
          setExam(await examApi.removeQuestion(deleting.id))
          toast.success(`Question ${deleting.full_label} deleted`)
        }}
      />
      <ConfirmDialog
        open={subFor !== null}
        onOpenChange={(open) => !open && setSubFor(null)}
        title={subFor ? `Split question ${subFor.label} into parts?` : ''}
        description="Once a question has parts, marks, model answers and rubrics belong to each part. This question's current marks, model answer and rubric will be removed."
        confirmLabel="Add part"
        onConfirm={async () => {
          if (!subFor) return
          setExam(await examApi.addQuestion(exam.id, { parent_id: subFor.id, text: '' }))
        }}
      />
    </StepCard>
  )
}
