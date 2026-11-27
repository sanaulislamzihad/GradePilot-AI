import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ScriptPicker } from '@/components/ScriptPicker'
import { AuthContext, type AuthContextValue } from '@/contexts/AuthContext'
import StudentExamPage from '@/pages/student/StudentExamPage'
import { studentApi } from '@/services/api'
import { makeUser } from '@/test/fixtures'
import type { StudentExamDetail, SubmissionDetail } from '@/types/api'

vi.mock('@/services/api', () => ({
  studentApi: { exam: vi.fn(), submit: vi.fn() },
  submissionApi: {},
}))

const pdf = (name = 'answers.pdf', size = 1000) => new File([new Uint8Array(size)], name, { type: 'application/pdf' })
const png = (name: string) => new File([new Uint8Array(500)], name, { type: 'image/png' })

function Picker({ formats = ['pdf', 'png', 'jpg', 'jpeg'], max = 5 * 1024 * 1024 }: { formats?: string[]; max?: number }) {
  const [files, setFiles] = useState<File[]>([])
  return <ScriptPicker files={files} onChange={setFiles} formats={formats} maxFileBytes={max} />
}

const input = (container: HTMLElement) => container.querySelector('input[type=file]') as HTMLInputElement

describe('script picker', () => {
  it('accepts page images in order and lets the student reorder them', async () => {
    const user = userEvent.setup()
    const { container } = render(<Picker />)
    await user.upload(input(container), [png('one.png'), png('two.png')])
    expect(screen.getByText('one.png')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Move two.png up' }))
    const names = screen.getAllByText(/\.png$/).map((el) => el.textContent)
    expect(names).toEqual(['Page 1two.png', 'Page 2one.png'])
  })

  it('refuses mixing a PDF with images', async () => {
    const user = userEvent.setup()
    const { container } = render(<Picker />)
    await user.upload(input(container), [png('one.png')])
    await user.upload(input(container), [pdf()])
    expect(screen.getByRole('alert')).toHaveTextContent('one PDF for the whole script')
    expect(screen.queryByText('answers.pdf')).not.toBeInTheDocument()
  })

  it('enforces the exam formats and size limit', async () => {
    const user = userEvent.setup({ applyAccept: false })
    const { container } = render(<Picker formats={['pdf']} max={500} />)
    await user.upload(input(container), [png('page.png')])
    expect(screen.getByRole('alert')).toHaveTextContent('not an accepted format')
    await user.upload(input(container), [pdf('big.pdf', 2000)])
    expect(screen.getByRole('alert')).toHaveTextContent('larger than')
  })
})

function examDetail(overrides: Partial<StudentExamDetail> = {}): StudentExamDetail {
  return {
    id: 'exam-1',
    slug: 'abc123',
    title: 'CSE445 Midterm',
    exam_type: 'midterm',
    course_code: 'CSE445',
    course_name: 'Machine Learning',
    section_name: '1',
    teacher_name: 'Ada Lovelace',
    total_marks: 20,
    submission_deadline: '2030-06-30T17:59:00Z',
    is_open: true,
    max_attempts: 2,
    attempts_used: 0,
    latest_submission: null,
    exam_date: null,
    instructions: 'Answer all questions.',
    allowed_formats: ['jpeg', 'jpg', 'pdf', 'png'],
    max_file_size_mb: 20,
    question_count: 4,
    can_submit: true,
    blocked_reason: null,
    attempts_left: 2,
    submissions: [],
    ...overrides,
  }
}

const receipt: SubmissionDetail = {
  id: 'sub-1',
  code: 'GP-K7PM2QXR',
  exam_id: 'exam-1',
  exam_title: 'CSE445 Midterm',
  course_code: 'CSE445',
  section_name: '1',
  student: { id: 'student-id', full_name: 'Sam Student', email: 'student@example.edu', student_number: '2021-001' },
  attempt_number: 1,
  is_latest: true,
  status: 'uploaded',
  status_message: null,
  file_count: 1,
  page_count: 3,
  total_size_bytes: 1000,
  submitted_at: '2026-11-26T10:00:00Z',
  max_attempts: 2,
  submission_deadline: '2030-06-30T17:59:00Z',
  files: [],
  processing_error: null,
  extraction_notes: null,
}

function renderExamPage() {
  const auth = { status: 'authenticated', user: makeUser('student') } as unknown as AuthContextValue
  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={['/student/exams/abc123']}>
        <Routes>
          <Route path="/student/exams/:slug" element={<StudentExamPage />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('student exam page', () => {
  beforeEach(() => vi.clearAllMocks())

  it('explains why a student cannot submit', async () => {
    vi.mocked(studentApi.exam).mockResolvedValue(
      examDetail({ can_submit: false, blocked_reason: 'The submission deadline has passed.', is_open: false }),
    )
    renderExamPage()
    expect(await screen.findByText('The submission deadline has passed.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Submit script' })).not.toBeInTheDocument()
  })

  it('submits, reuses the idempotency key on retry and shows the receipt', async () => {
    const user = userEvent.setup()
    vi.mocked(studentApi.exam).mockResolvedValue(examDetail())
    vi.mocked(studentApi.submit)
      .mockRejectedValueOnce(Object.assign(new Error('network'), { isAxiosError: true, response: undefined }))
      .mockResolvedValueOnce(receipt)
    const { container } = renderExamPage()

    await screen.findByRole('heading', { name: 'CSE445 Midterm' })
    expect(screen.getByText('2021-001')).toBeInTheDocument()
    await user.upload(input(container), [pdf()])
    await user.click(screen.getByRole('button', { name: 'Submit script' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Submit' }))
    expect(await screen.findAllByText(/Cannot reach the server/)).not.toHaveLength(0)

    // Retry the same upload: the request must carry the same key.
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Submit' }))
    await waitFor(() => expect(studentApi.submit).toHaveBeenCalledTimes(2))
    const [first, second] = vi.mocked(studentApi.submit).mock.calls
    expect(second![2]).toBe(first![2])
    expect(await screen.findByText('GP-K7PM2QXR')).toBeInTheDocument()
    expect(screen.getByText('Your script was submitted')).toBeInTheDocument()
  })
})
