import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ProvidersSection } from '@/pages/teacher/ai/ProvidersSection'
import { ExtractionEditor } from '@/pages/teacher/submission/ExtractionEditor'
import { ReviewPanel } from '@/pages/teacher/submission/ReviewPanel'
import { aiApi, processingApi, reviewApi } from '@/services/api'
import type { Evaluation, ExtractionView, Provider, SubmissionDetail } from '@/types/api'

vi.mock('@/services/api', () => ({
  aiApi: { connect: vi.fn(), test: vi.fn(), removeProvider: vi.fn() },
  processingApi: { correctAnswers: vi.fn() },
  reviewApi: { save: vi.fn(), approve: vi.fn(), reopen: vi.fn(), reject: vi.fn(), verify: vi.fn(), history: vi.fn() },
}))

const SECRET = 'sk-live-very-secret-key-4242'

describe('provider keys', () => {
  it('sends the key once from a password field and shows only the masked hint', async () => {
    const user = userEvent.setup()
    const providers: Provider[] = [{ slug: 'openai', name: 'OpenAI', requires_base_url: false, connection: null }]
    const connected: Provider = {
      ...providers[0]!,
      connection: { id: 'k1', key_hint: '…4242', base_url: null, status: 'valid', last_tested_at: null, last_error: null, created_at: '' },
    }
    vi.mocked(aiApi.connect).mockResolvedValue(connected)
    const onChange = vi.fn()
    const { container, rerender } = render(<ProvidersSection providers={providers} onChange={onChange} />)

    await user.click(screen.getByRole('button', { name: /Connect/ }))
    const field = screen.getByLabelText('API key')
    expect(field).toHaveAttribute('type', 'password')
    await user.type(field, SECRET)
    await user.click(screen.getByRole('button', { name: 'Test and save' }))

    await waitFor(() => expect(aiApi.connect).toHaveBeenCalledWith('openai', SECRET, undefined))
    expect(onChange).toHaveBeenCalledWith(connected)
    rerender(<ProvidersSection providers={[connected]} onChange={onChange} />)
    expect(screen.getByText('…4242')).toBeInTheDocument()
    expect(container.innerHTML).not.toContain(SECRET)
  })
})

const evaluation: Evaluation = {
  id: 'e1', submission_id: 's1', run_number: 1, is_current: true, status: 'completed',
  provider: 'openai', model: 'gpt-test', total_awarded: null, total_max: 15, final_total: null,
  flags: ['evidence_not_found', 'incomplete', 'verifier_disagrees'], started_at: '', completed_at: '2026-11-27T10:00:00Z',
  verification_status: 'completed', review_status: 'pending', teacher_comment: null, reviewed_by: null, reviewed_at: null,
  questions: [
    {
      question_id: 'q1', label: '1', question_type: 'descriptive', answer_status: 'answered', awarded: 4, teacher_awarded: null,
      final_awarded: 4, max_marks: 5, feedback: 'Good definition.', missing_concepts: [], flags: ['evidence_not_found', 'verifier_disagrees'],
      similarity: 0.71, math_check: null, teacher_comment: null, answer_text: 'ML learns from data.',
      criteria: [{
        id: 'c1', name: 'Definition', max_marks: 5, awarded: 4, teacher_awarded: null, final_awarded: 4,
        explanation: 'Mostly correct.', missing_concepts: ['example'],
        evidence: [{ quote: 'learns from data', found_in_answer: true }, { quote: 'deep learning', found_in_answer: false }],
      }],
      verification: {
        provider: 'anthropic', model: 'claude-test', same_model_as_evaluator: false, verdict: 'disagrees', suggested_awarded: 2,
        rubric_followed: true, evidence_supports_marks: false, missed_valid_concepts: [], unsupported_assumptions: [],
        criterion_notes: [{ criterion: 'Definition', fair: false, suggested_awarded: 2, note: 'No example given.' }], comment: null,
      },
    },
    {
      question_id: 'q2', label: '2(a)', question_type: 'mathematical', answer_status: 'unreadable', awarded: null, teacher_awarded: null,
      final_awarded: null, max_marks: 10, feedback: null, missing_concepts: [], flags: ['unreadable_answer'],
      similarity: null, math_check: null, teacher_comment: null, answer_text: '', criteria: [], verification: null,
    },
  ],
}

const submission = { id: 's1', status: 'teacher_review_required' } as SubmissionDetail

describe('review panel', () => {
  it('shows AI marks, checks and evidence, and saves teacher marks', async () => {
    const user = userEvent.setup()
    vi.mocked(reviewApi.save).mockResolvedValue({ ...evaluation, final_total: 12 })
    vi.mocked(reviewApi.history).mockResolvedValue([])
    const onEvaluation = vi.fn()
    render(<ReviewPanel evaluation={evaluation} submission={submission} onEvaluation={onEvaluation} onSubmission={vi.fn()} />)

    expect(screen.getAllByText('Verifier disagrees').length).toBeGreaterThan(0)
    expect(screen.getByText('Suggests 2 / 5')).toBeInTheDocument()
    expect(screen.getByText('The verifier thinks the evidence does not support the marks.')).toBeInTheDocument()
    expect(screen.getByLabelText('Not found in the answer')).toBeInTheDocument()
    expect(screen.getByText('Similarity to the model answer: 71% (signal only)')).toBeInTheDocument()

    const mark = screen.getByLabelText('Your mark for 1 Definition')
    await user.type(mark, '9')
    expect(mark).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('button', { name: /Save and approve/ })).toBeDisabled()
    await user.clear(mark)
    await user.type(mark, '3')
    const questionMarks = screen.getAllByLabelText('Question mark')
    await user.type(questionMarks[1]!, '8')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() => expect(reviewApi.save).toHaveBeenCalled())
    const [, payload] = vi.mocked(reviewApi.save).mock.calls[0]!
    expect(payload).toEqual([
      { question_id: 'q1', criteria: [{ criterion_id: 'c1', teacher_awarded: 3 }], teacher_awarded: null, teacher_comment: null },
      { question_id: 'q2', criteria: [], teacher_awarded: 8, teacher_comment: null },
    ])
    expect(onEvaluation).toHaveBeenCalledWith(expect.objectContaining({ final_total: 12 }))
  })

  it('is read-only once approved and offers reopening', () => {
    vi.mocked(reviewApi.history).mockResolvedValue([])
    render(
      <ReviewPanel
        evaluation={{ ...evaluation, review_status: 'approved', final_total: 12, reviewed_by: 'Ada' }}
        submission={{ ...submission, status: 'approved' }}
        onEvaluation={vi.fn()}
        onSubmission={vi.fn()}
      />,
    )
    expect(screen.getByLabelText('Your mark for 1 Definition')).toBeDisabled()
    expect(screen.queryByRole('button', { name: /Approve marks/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Reopen/ })).toBeInTheDocument()
  })
})

describe('extraction review', () => {
  it('confirms every answer with the corrections applied', async () => {
    const user = userEvent.setup()
    const view: ExtractionView = {
      status: 'ocr_review_required',
      extraction_notes: 'No answer found for question 2(a).',
      answers: [
        { question_id: 'q1', label: '1', question_text: 'Explain ML.', max_marks: 5, text: 'Machine leaming', status: 'answered',
          source: 'ai_ocr', confidence: 0.55, pages: [1], unreadable_notes: ['one word on line 2'], needs_review: true },
        { question_id: 'q2', label: '2(a)', question_text: 'Define it.', max_marks: 10, text: '', status: 'missing',
          source: 'ai_ocr', confidence: 1, pages: [], unreadable_notes: [], needs_review: false },
      ],
    }
    vi.mocked(processingApi.correctAnswers).mockResolvedValue({ ...view, status: 'ready_for_evaluation' })
    const onSaved = vi.fn()
    render(<ExtractionEditor submissionId="s1" view={view} onSaved={onSaved} />)

    expect(screen.getByText('55% confident', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('Could not read: one word on line 2')).toBeInTheDocument()
    const box = screen.getByLabelText('Answer text for question 1')
    await user.clear(box)
    await user.type(box, 'Machine learning')
    await user.click(screen.getByRole('button', { name: 'Confirm answers and mark' }))

    await waitFor(() =>
      expect(processingApi.correctAnswers).toHaveBeenCalledWith(
        's1',
        [
          { question_id: 'q1', text: 'Machine learning', status: 'answered' },
          { question_id: 'q2', text: '', status: 'missing' },
        ],
        true,
      ),
    )
    expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ status: 'ready_for_evaluation' }), true)
    expect(within(screen.getByLabelText('Status of question 2(a)')).getByRole('option', { name: 'Not answered' })).toBeInTheDocument()
  })
})
