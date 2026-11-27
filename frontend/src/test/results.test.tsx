import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { niceTicks } from '@/components/charts/scale'
import { AuthContext, type AuthContextValue } from '@/contexts/AuthContext'
import ResultDetailPage from '@/pages/shared/ResultDetailPage'
import AnalyticsPage from '@/pages/teacher/results/AnalyticsPage'
import ResultsPage from '@/pages/teacher/results/ResultsPage'
import { examApi, resultsApi } from '@/services/api'
import { makeUser } from '@/test/fixtures'
import type { ExamAnalytics, ExamResults, ResultView, UserRole } from '@/types/api'

vi.mock('@/services/api', () => ({
  examApi: { list: vi.fn() },
  resultsApi: {
    forExam: vi.fn(),
    saveSettings: vi.fn(),
    publish: vi.fn(),
    withdraw: vi.fn(),
    publishAll: vi.fn(),
    get: vi.fn(),
    analytics: vi.fn(),
    resultPdf: vi.fn(),
    resultsCsv: vi.fn(),
    classReport: vi.fn(),
  },
}))

function renderAt(role: UserRole, path: string, pattern: string, element: ReactNode) {
  const auth = { status: 'authenticated', user: makeUser(role) } as unknown as AuthContextValue
  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={pattern} element={element} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

const examList = {
  items: [{ id: 'exam-1', title: 'CSE445 Midterm', course_code: 'CSE445', submission_count: 2 }],
  total: 1,
  page: 1,
  page_size: 100,
}

const results: ExamResults = {
  exam_id: 'exam-1',
  exam_title: 'CSE445 Midterm',
  result_release_mode: 'after_approval',
  release_teacher_comments: true,
  approved_unpublished: 1,
  rows: [
    {
      submission_id: 's1', submission_code: 'GP-AAA', student_name: 'Nadia Islam', student_number: '2021-0077',
      status: 'approved', final_total: 15.75, max_marks: 20, percentage: 78.75, published: false, published_at: null,
    },
    {
      submission_id: 's2', submission_code: 'GP-BBB', student_name: 'Rafi Ahmed', student_number: '2021-0088',
      status: 'teacher_review_required', final_total: 6.75, max_marks: 20, percentage: 33.75, published: false, published_at: null,
    },
  ],
}

describe('teacher results page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(examApi.list).mockResolvedValue(examList as never)
    vi.mocked(resultsApi.forExam).mockResolvedValue(results)
  })

  it('only offers publishing for approved results', async () => {
    renderAt('teacher', '/teacher/results?exam=exam-1', '/teacher/results', <ResultsPage />)
    const nadia = (await screen.findByText('Nadia Islam')).closest('tr')!
    const rafi = screen.getByText('Rafi Ahmed').closest('tr')!
    expect(within(nadia).getByRole('button', { name: 'Publish' })).toBeInTheDocument()
    expect(within(rafi).queryByRole('button', { name: 'Publish' })).not.toBeInTheDocument()
    expect(within(rafi).getByText('Awaiting approval')).toBeInTheDocument()

    vi.mocked(resultsApi.publish).mockResolvedValue({} as ResultView)
    await userEvent.click(within(nadia).getByRole('button', { name: 'Publish' }))
    expect(resultsApi.publish).toHaveBeenCalledWith('s1')
    await waitFor(() => expect(resultsApi.forExam).toHaveBeenCalledTimes(2))
  })

  it('saves the release mode', async () => {
    const user = userEvent.setup()
    vi.mocked(resultsApi.saveSettings).mockImplementation(async (_id, s) => s)
    renderAt('teacher', '/teacher/results?exam=exam-1', '/teacher/results', <ResultsPage />)
    const save = await screen.findByRole('button', { name: 'Save settings' })
    expect(save).toBeDisabled()
    await user.click(screen.getByText('Show provisional marks'))
    await user.click(screen.getByLabelText(/Include my review comments/))
    await user.click(save)
    expect(resultsApi.saveSettings).toHaveBeenCalledWith('exam-1', {
      result_release_mode: 'provisional',
      release_teacher_comments: false,
    })
  })
})

const analytics: ExamAnalytics = {
  exam_id: 'exam-1', exam_title: 'CSE445 Midterm', total_marks: 20, total_students: 3, total_submissions: 3,
  pending_evaluations: 1, approved_results: 0, published_results: 2, graded_count: 2,
  average: 11.25, median: 11.25, highest: 15.75, lowest: 6.75, average_percentage: 56.3,
  distribution: Array.from({ length: 10 }, (_, i) => ({ label: `${i * 10}–${(i + 1) * 10}%`, count: i === 3 || i === 7 ? 1 : 0 })),
  questions: [
    { label: '1', text: 'Explain ML', max_marks: 5, average: 3.75, average_percentage: 75, answered: 2 },
    { label: '3', text: 'Solve 2x + 3 = 11', max_marks: 5, average: 1.88, average_percentage: 37.5, answered: 1 },
  ],
  weakest_questions: [{ label: '3', text: 'Solve 2x + 3 = 11', max_marks: 5, average: 1.88, average_percentage: 37.5, answered: 1 }],
  common_missing_concepts: [{ concept: 'a concrete example', count: 2 }],
}

describe('analytics page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(examApi.list).mockResolvedValue(examList as never)
  })

  it('shows statistics from approved marks with a table view of each chart', async () => {
    vi.mocked(resultsApi.analytics).mockResolvedValue(analytics)
    renderAt('teacher', '/teacher/analytics?exam=exam-1', '/teacher/analytics', <AnalyticsPage />)
    expect(await screen.findAllByText('11.25 / 20')).toHaveLength(2)
    expect(screen.getByText('2 of 3')).toBeInTheDocument()
    expect(screen.getByText('2 students')).toBeInTheDocument()

    await userEvent.click(screen.getAllByRole('button', { name: 'Show table' })[1]!)
    expect(screen.getByRole('cell', { name: 'Q3' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '1.88 / 5 (37.5%)' })).toBeInTheDocument()
  })

  it('explains when nothing has been approved yet', async () => {
    vi.mocked(resultsApi.analytics).mockResolvedValue({ ...analytics, graded_count: 0, average: null })
    renderAt('teacher', '/teacher/analytics?exam=exam-1', '/teacher/analytics', <AnalyticsPage />)
    expect(await screen.findByText('No approved results yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Go to AI Evaluation' })).toHaveAttribute('href', '/teacher/evaluation?exam=exam-1')
  })
})

const view: ResultView = {
  submission_id: 's2', submission_code: 'GP-BBB', exam_id: 'exam-1', exam_title: 'CSE445 Midterm', course_code: 'CSE445',
  section_name: '1', student_name: 'Rafi Ahmed', student_number: '2021-0088', provisional: true, total: 6.75, max_marks: 20,
  percentage: 33.75, published_at: null, teacher_comment: null,
  questions: [
    {
      label: '1', text: 'Explain ML', max_marks: 5, awarded: 3.75, answered: true, feedback: 'Add an example.',
      missing_concepts: ['a concrete example'], teacher_comment: null,
      criteria: [{ name: 'Correct definition', max_marks: 2, awarded: 1.5, explanation: 'One point missing.', missing_concepts: [] }],
    },
  ],
}

describe('result detail', () => {
  beforeEach(() => vi.clearAllMocks())

  it('labels provisional marks for the student', async () => {
    vi.mocked(resultsApi.get).mockResolvedValue(view)
    renderAt('student', '/student/results/s2', '/student/results/:submissionId', <ResultDetailPage />)
    expect(await screen.findByText(/have not been confirmed by your teacher/)).toBeInTheDocument()
    expect(screen.getByText('Correct definition')).toBeInTheDocument()
    expect(screen.getByText('a concrete example')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /My Results/ })).toHaveAttribute('href', '/student/results')
  })

  it('shows the final result with the teacher comment', async () => {
    vi.mocked(resultsApi.get).mockResolvedValue({ ...view, provisional: false, published_at: '2026-11-27T10:00:00Z', teacher_comment: 'Well organised.' })
    renderAt('student', '/student/results/s2', '/student/results/:submissionId', <ResultDetailPage />)
    expect(await screen.findByText('Well organised.')).toBeInTheDocument()
    expect(screen.getByText('Final')).toBeInTheDocument()
    expect(screen.queryByText(/have not been confirmed/)).not.toBeInTheDocument()
  })
})

describe('chart scale', () => {
  it('rounds the axis up to clean ticks', () => {
    expect(niceTicks(1)).toEqual([0, 0.25, 0.5, 0.75, 1])
    expect(niceTicks(7)).toEqual([0, 2, 4, 6, 8])
    expect(niceTicks(100)).toEqual([0, 25, 50, 75, 100])
    expect(niceTicks(0)).toEqual([0, 1])
  })
})
