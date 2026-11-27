import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { MarksStep } from '@/pages/teacher/exams/steps/MarksStep'
import { PublishStep } from '@/pages/teacher/exams/steps/PublishStep'
import { RubricsStep } from '@/pages/teacher/exams/steps/RubricsStep'
import { ExamWorkspaceContext, leafQuestions } from '@/pages/teacher/exams/workspace'
import { examApi } from '@/services/api'
import type { ExamDetail, Question } from '@/types/api'
import { formatMarks, fromLocalInput, hasTwoDecimalsAtMost, toLocalInput } from '@/utils/format'

vi.mock('@/services/api', () => ({
  examApi: { saveMarks: vi.fn(), saveRubric: vi.fn(), publish: vi.fn() },
  aiApi: { modelConfigs: vi.fn().mockResolvedValue([]) },
}))

function question(overrides: Partial<Question>): Question {
  return {
    id: overrides.label ?? 'q',
    parent_id: null,
    label: '1',
    full_label: overrides.label ?? '1',
    position: 1,
    text: 'Explain machine learning.',
    question_type: 'descriptive',
    marks: null,
    is_leaf: true,
    model_answer: null,
    rubric: null,
    children: [],
    ...overrides,
  }
}

function exam(overrides: Partial<ExamDetail> = {}): ExamDetail {
  const questions = overrides.questions ?? [
    question({ id: 'q1', label: '1', full_label: '1', marks: 4 }),
    question({ id: 'q2', label: '2', full_label: '2', marks: null }),
  ]
  return {
    id: 'exam-1',
    title: 'CSE445 Midterm',
    exam_type: 'midterm',
    status: 'draft',
    course_id: null,
    course_code: null,
    course_name: null,
    section_id: null,
    section_name: null,
    total_marks: 10,
    exam_date: null,
    submission_deadline: '2030-01-01T10:00:00Z',
    question_count: questions.length,
    submission_count: 0,
    created_at: '2026-11-25T10:00:00Z',
    updated_at: '2026-11-25T10:00:00Z',
    published_at: null,
    result_release_mode: 'after_approval',
    release_teacher_comments: true,
    instructions: null,
    allowed_formats: ['pdf'],
    max_file_size_mb: 20,
    max_attempts: 1,
    public_slug: null,
    documents: [],
    readiness: {
      ready: false,
      allocated_marks: 4,
      total_marks: 10,
      checks: [
        { key: 'details', label: 'Exam details', ok: true, detail: 'Complete' },
        { key: 'questions', label: 'Questions', ok: true, detail: '2 gradable questions' },
        { key: 'marks', label: 'Marks', ok: false, detail: 'Assign marks to question 2' },
        { key: 'model_answers', label: 'Model answers', ok: false, detail: '0 of 2 approved' },
        { key: 'rubrics', label: 'Marking rubrics', ok: false, detail: '0 of 2 approved' },
      ],
    },
    ...overrides,
    questions,
  }
}

function renderStep(node: ReactNode, value: ExamDetail, setExam = vi.fn()) {
  return render(
    <MemoryRouter>
      <ExamWorkspaceContext.Provider value={{ exam: value, setExam, editable: value.status === 'draft' }}>{node}</ExamWorkspaceContext.Provider>
    </MemoryRouter>,
  )
}

describe('marks step', () => {
  it('tracks the running total against the exam total and saves', async () => {
    const user = userEvent.setup()
    const setExam = vi.fn()
    vi.mocked(examApi.saveMarks).mockResolvedValue(exam())
    renderStep(<MarksStep />, exam(), setExam)

    expect(screen.getByText('6 still to allocate', { exact: false })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Marks for question 2'), '7')
    expect(screen.getByText('1 over the exam total', { exact: false })).toBeInTheDocument()

    await user.clear(screen.getByLabelText('Marks for question 2'))
    await user.type(screen.getByLabelText('Marks for question 2'), '6')
    expect(screen.getByText('allocated — matches the exam total', { exact: false })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Save marks' }))
    await waitFor(() =>
      expect(examApi.saveMarks).toHaveBeenCalledWith('exam-1', [
        { question_id: 'q1', marks: 4 },
        { question_id: 'q2', marks: 6 },
      ]),
    )
    expect(setExam).toHaveBeenCalled()
  })

  it('blocks saving invalid marks', async () => {
    const user = userEvent.setup()
    renderStep(<MarksStep />, exam())
    await user.type(screen.getByLabelText('Marks for question 2'), '1.234')
    expect(screen.getByText(/at most two decimals/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save marks' })).toBeDisabled()
  })

  it('is read-only while the exam is published', () => {
    renderStep(<MarksStep />, exam({ status: 'published' }))
    expect(screen.getByLabelText('Marks for question 1')).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Save marks' })).not.toBeInTheDocument()
  })
})

describe('rubrics step', () => {
  it('only allows approval when criteria add up to the question marks', async () => {
    const user = userEvent.setup()
    const value = exam({ questions: [question({ id: 'q1', label: '1', full_label: '1', marks: 5 })] })
    renderStep(<RubricsStep />, value)

    await user.type(screen.getByLabelText('Criterion 1 name'), 'Definition')
    await user.type(screen.getByLabelText('Criterion 1 marks'), '2')
    const approve = screen.getByRole('button', { name: 'Approve rubric' })
    expect(approve).toBeDisabled()
    expect(screen.getByText('Total 2 / 5')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Add criterion' }))
    await user.type(screen.getByLabelText('Criterion 2 name'), 'Example')
    await user.type(screen.getByLabelText('Criterion 2 marks'), '3')
    expect(screen.getByText('Total 5 / 5')).toBeInTheDocument()
    expect(approve).toBeEnabled()

    vi.mocked(examApi.saveRubric).mockResolvedValue(value)
    await user.click(approve)
    await waitFor(() =>
      expect(examApi.saveRubric).toHaveBeenCalledWith(
        'q1',
        [
          { name: 'Definition', description: null, max_marks: 2 },
          { name: 'Example', description: null, max_marks: 3 },
        ],
        true,
      ),
    )
  })
})

describe('publish step', () => {
  it('lists failing checks and keeps publishing disabled until ready', () => {
    renderStep(<PublishStep />, exam())
    expect(screen.getByRole('button', { name: /Publish exam/ })).toBeDisabled()
    expect(screen.getByText('Assign marks to question 2')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Fix' })).toHaveLength(3)
  })

  it('enables publishing when every check passes', () => {
    const ready = exam()
    ready.readiness = { ...ready.readiness, ready: true, checks: ready.readiness.checks.map((c) => ({ ...c, ok: true })) }
    renderStep(<PublishStep />, ready)
    expect(screen.getByRole('button', { name: /Publish exam/ })).toBeEnabled()
    expect(screen.queryByRole('link', { name: 'Fix' })).not.toBeInTheDocument()
  })
})

describe('helpers', () => {
  it('flattens sub-questions into gradable questions', () => {
    const parent = question({
      id: 'q2', label: '2', is_leaf: false,
      children: [question({ id: 'a', label: 'a', full_label: '2(a)' }), question({ id: 'b', label: 'b', full_label: '2(b)' })],
    })
    const value = exam({ questions: [question({ id: 'q1' }), parent] })
    expect(leafQuestions(value).map((q) => q.full_label)).toEqual(['1', '2(a)', '2(b)'])
  })

  it('formats and validates marks', () => {
    expect(formatMarks(5)).toBe('5')
    expect(formatMarks(2.5)).toBe('2.5')
    expect(formatMarks(null)).toBe('—')
    expect(hasTwoDecimalsAtMost(0.29)).toBe(true)
    expect(hasTwoDecimalsAtMost(1.234)).toBe(false)
  })

  it('round-trips datetime-local values through ISO timestamps', () => {
    const iso = '2030-03-15T09:30:00.000Z'
    expect(fromLocalInput(toLocalInput(iso))).toBe(iso)
    expect(fromLocalInput('')).toBeNull()
  })
})
