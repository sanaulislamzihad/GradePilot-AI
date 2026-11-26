import { createContext, useContext } from 'react'
import type { ExamDetail, Question } from '@/types/api'

export interface ExamWorkspaceValue {
  exam: ExamDetail
  setExam: (exam: ExamDetail) => void
  /** False while the exam is published: every editing control is disabled. */
  editable: boolean
}

export const ExamWorkspaceContext = createContext<ExamWorkspaceValue | null>(null)

export function useExamWorkspace() {
  const value = useContext(ExamWorkspaceContext)
  if (!value) throw new Error('useExamWorkspace must be used inside the exam workspace')
  return value
}

/** Gradable questions in paper order: sub-questions, or the question itself when it has none. */
export function leafQuestions(exam: ExamDetail): Question[] {
  return exam.questions.flatMap((q) => (q.children.length ? q.children : [q]))
}

export const steps = [
  { key: 'details', label: 'Details', check: 'details' },
  { key: 'paper', label: 'Question paper', check: null },
  { key: 'questions', label: 'Questions', check: 'questions' },
  { key: 'marks', label: 'Marks', check: 'marks' },
  { key: 'answers', label: 'Model answers', check: 'model_answers' },
  { key: 'rubrics', label: 'Rubrics', check: 'rubrics' },
  { key: 'publish', label: 'Publish', check: null },
] as const

export type StepKey = (typeof steps)[number]['key']

export function stepDone(exam: ExamDetail, key: StepKey): boolean {
  const step = steps.find((s) => s.key === key)!
  if (key === 'paper') return exam.documents.some((d) => d.kind === 'question_paper') || exam.questions.length > 0
  if (key === 'publish') return exam.status === 'published'
  return exam.readiness.checks.find((c) => c.key === step.check)?.ok ?? false
}
