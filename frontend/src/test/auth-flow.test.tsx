import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '@/App'
import { AuthProvider } from '@/contexts/AuthContext'
import { authApi, dashboardApi } from '@/services/api'
import { refreshSession } from '@/services/http'
import { makeSession } from '@/test/fixtures'
import type { TokenResponse } from '@/types/api'

vi.mock('@/services/http', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/http')>()
  return { ...actual, refreshSession: vi.fn(), setAccessToken: vi.fn(), bindSessionListener: vi.fn() }
})

vi.mock('@/services/api', () => ({
  authApi: { login: vi.fn(), register: vi.fn(), logout: vi.fn(), me: vi.fn() },
  dashboardApi: { teacher: vi.fn(), student: vi.fn() },
  courseApi: {},
  studentApi: { enrollments: vi.fn().mockResolvedValue([]) },
  adminApi: {},
  profileApi: {},
}))

const teacherDashboard = {
  course_count: 2,
  section_count: 3,
  student_count: 41,
  exam_count: 0,
  published_exam_count: 0,
  draft_exam_count: 0,
  submission_count: 0,
  courses: [],
  recent_exams: [],
  recent_activity: [],
}
const studentDashboard = {
  enrollment_count: 0,
  course_count: 0,
  available_exam_count: 0,
  submitted_exam_count: 0,
  upcoming_exams: [],
  enrollments: [],
  recent_activity: [],
}

function renderApp(path: string, session: TokenResponse | null) {
  vi.mocked(refreshSession).mockImplementation(() =>
    session ? Promise.resolve(session) : Promise.reject(new Error('no session')),
  )
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(dashboardApi.teacher).mockResolvedValue(teacherDashboard)
  vi.mocked(dashboardApi.student).mockResolvedValue(studentDashboard)
})

describe('route protection', () => {
  it('sends anonymous visitors to the login page', async () => {
    renderApp('/teacher', null)
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('redirects a student away from the teacher area', async () => {
    renderApp('/teacher/courses', makeSession('student'))
    expect(await screen.findByRole('heading', { name: /Welcome, Sam/ })).toBeInTheDocument()
    expect(dashboardApi.teacher).not.toHaveBeenCalled()
  })

  it('sends signed-in users from the login page to their dashboard', async () => {
    renderApp('/login', makeSession('teacher'))
    expect(await screen.findByRole('heading', { name: /Welcome, Ada/ })).toBeInTheDocument()
  })
})

describe('teacher dashboard', () => {
  it('shows counts from the API and only implemented navigation', async () => {
    renderApp('/teacher', makeSession('teacher'))
    expect(await screen.findByText('41')).toBeInTheDocument()

    const nav = screen.getAllByRole('navigation', { name: 'Main' })[0]!
    const links = Array.from(nav.querySelectorAll('a')).map((a) => a.textContent)
    expect(links).toEqual(['Dashboard', 'My Exams', 'Create Exam', 'Submissions', 'AI Evaluation', 'Courses', 'AI Settings', 'Profile'])
  })
})

describe('login', () => {
  it('validates input before calling the API', async () => {
    const user = userEvent.setup()
    renderApp('/login', null)
    await user.click(await screen.findByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Email is required')).toBeInTheDocument()
    expect(screen.getByText('Password is required')).toBeInTheDocument()
    expect(authApi.login).not.toHaveBeenCalled()
  })

  it('signs in and opens the dashboard for the user role', async () => {
    const user = userEvent.setup()
    vi.mocked(authApi.login).mockResolvedValue(makeSession('teacher'))
    renderApp('/login', null)

    await user.type(await screen.findByLabelText('Email'), 'teacher@example.edu')
    await user.type(screen.getByLabelText('Password'), 'Passw0rd!')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => expect(authApi.login).toHaveBeenCalledWith('teacher@example.edu', 'Passw0rd!'))
    expect(await screen.findByRole('heading', { name: /Welcome, Ada/ })).toBeInTheDocument()
  })

  it('shows the server error message on failure', async () => {
    const user = userEvent.setup()
    vi.mocked(authApi.login).mockRejectedValue(
      Object.assign(new Error('401'), {
        isAxiosError: true,
        response: { status: 401, data: { detail: 'Incorrect email or password' } },
      }),
    )
    renderApp('/login', null)
    await user.type(await screen.findByLabelText('Email'), 'teacher@example.edu')
    await user.type(screen.getByLabelText('Password'), 'wrong-pass1')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password')
  })
})

describe('registration', () => {
  it('requires a student ID only for students', async () => {
    const user = userEvent.setup()
    renderApp('/register', null)
    expect(await screen.findByRole('heading', { name: 'Create your account' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Student ID')).not.toBeInTheDocument()

    await user.click(screen.getByRole('radio', { name: /Student/ }))
    expect(screen.getByLabelText('Student ID')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Full name'), 'Sam Student')
    await user.type(screen.getByLabelText('Email'), 'sam@example.edu')
    await user.type(screen.getByLabelText('Password'), 'Passw0rd1')
    await user.type(screen.getByLabelText('Confirm password'), 'Passw0rd1')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByText('Enter your institution student ID')).toBeInTheDocument()
    expect(authApi.register).not.toHaveBeenCalled()
  })

  it('flags mismatched passwords', async () => {
    const user = userEvent.setup()
    renderApp('/register', null)
    await user.type(await screen.findByLabelText('Full name'), 'Ada Teacher')
    await user.type(screen.getByLabelText('Email'), 'ada@example.edu')
    await user.type(screen.getByLabelText('Password'), 'Passw0rd1')
    await user.type(screen.getByLabelText('Confirm password'), 'Different1')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument()
  })
})

describe('return after sign-in', () => {
  it('opens the page that required sign-in once the student signs in', async () => {
    const user = userEvent.setup()
    vi.mocked(authApi.login).mockResolvedValue(makeSession('student'))
    renderApp('/student/courses', null)
    await user.type(await screen.findByLabelText('Email'), 'student@example.edu')
    await user.type(screen.getByLabelText('Password'), 'Passw0rd!')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('heading', { name: 'My Courses' })).toBeInTheDocument()
  })
})
