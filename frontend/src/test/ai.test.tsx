import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ProvidersSection } from '@/pages/teacher/ai/ProvidersSection'
import { EvaluationView } from '@/pages/teacher/submission/EvaluationView'
import { ExtractionEditor } from '@/pages/teacher/submission/ExtractionEditor'
import { aiApi, processingApi } from '@/services/api'
import type { Evaluation, ExtractionView, Provider } from '@/types/api'

vi.mock('@/services/api', () => ({
  aiApi: { connect: vi.fn(), test: vi.fn(), removeProvider: vi.fn() },
  processingApi: { correctAnswers: vi.fn() },
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
  provider: 'openai', model: 'gpt-test', total_awarded: null, total_max: 15,
  flags: ['evidence_not_found', 'incomplete', 'missing_answer'], started_at: '', completed_at: '2026-11-27T10:00:00Z',
  questions: [
    {
      question_id: 'q1', label: '1', answer_status: 'answered', awarded: 4, max_marks: 5, feedback: 'Good definition.',
      missing_concepts: [], flags: ['evidence_not_found'], answer_text: 'ML learns from data.',
      criteria: [{
        name: 'Definition', max_marks: 5, awarded: 4, explanation: 'Mostly correct.', missing_concepts: ['example'],
        evidence: [{ quote: 'learns from data', found_in_answer: true }, { quote: 'deep learning', found_in_answer: false }],
      }],
    },
    {
      question_id: 'q2', label: '2(a)', answer_status: 'unreadable', awarded: null, max_marks: 10, feedback: null,
      missing_concepts: [], flags: ['unreadable_answer'], answer_text: '', criteria: [],
    },
  ],
}

describe('evaluation view', () => {
  it('shows suggested marks, flags and whether each evidence quote was found', () => {
    render(<EvaluationView evaluation={evaluation} />)
    expect(screen.getByText('AI-suggested marks')).toBeInTheDocument()
    expect(screen.getAllByText('—').length).toBeGreaterThan(0) // no total while a question is ungraded
    expect(screen.getAllByText('Some questions need your marks').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Unreadable — mark it yourself').length).toBeGreaterThan(0)
    expect(screen.getByLabelText('Found in the answer')).toBeInTheDocument()
    expect(screen.getByLabelText('Not found in the answer')).toBeInTheDocument()
    expect(screen.getByText('Missing: example')).toBeInTheDocument()
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
