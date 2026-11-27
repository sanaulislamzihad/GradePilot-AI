import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router'
import { LoadingState } from '@/components/ui/States'
import { AppLayout } from '@/layouts/AppLayout'
import { GuestOnly, RequireRole } from '@/layouts/RouteGuards'
import LandingPage from '@/pages/LandingPage'
import NotFoundPage from '@/pages/NotFoundPage'
import PublicExamPage from '@/pages/PublicExamPage'
import LoginPage from '@/pages/auth/LoginPage'
import RegisterPage from '@/pages/auth/RegisterPage'

// Role areas are split into separate chunks; visitors only download what they use.
const ProfilePage = lazy(() => import('@/pages/shared/ProfilePage'))
const TeacherDashboard = lazy(() => import('@/pages/teacher/TeacherDashboard'))
const CoursesPage = lazy(() => import('@/pages/teacher/CoursesPage'))
const CourseDetailPage = lazy(() => import('@/pages/teacher/CourseDetailPage'))
const ExamsPage = lazy(() => import('@/pages/teacher/exams/ExamsPage'))
const CreateExamPage = lazy(() => import('@/pages/teacher/exams/CreateExamPage'))
const ExamWorkspacePage = lazy(() => import('@/pages/teacher/exams/ExamWorkspacePage'))
const StudentDashboard = lazy(() => import('@/pages/student/StudentDashboard'))
const StudentCoursesPage = lazy(() => import('@/pages/student/StudentCoursesPage'))
const AvailableExamsPage = lazy(() => import('@/pages/student/AvailableExamsPage'))
const StudentExamPage = lazy(() => import('@/pages/student/StudentExamPage'))
const MySubmissionsPage = lazy(() => import('@/pages/student/MySubmissionsPage'))
const SubmissionDetailPage = lazy(() => import('@/pages/shared/SubmissionDetailPage'))
const SubmissionsPage = lazy(() => import('@/pages/teacher/SubmissionsPage'))
const AISettingsPage = lazy(() => import('@/pages/teacher/ai/AISettingsPage'))
const EvaluationQueuePage = lazy(() => import('@/pages/teacher/EvaluationQueuePage'))
const ResultsPage = lazy(() => import('@/pages/teacher/results/ResultsPage'))
const AnalyticsPage = lazy(() => import('@/pages/teacher/results/AnalyticsPage'))
const ResultDetailPage = lazy(() => import('@/pages/shared/ResultDetailPage'))
const MyResultsPage = lazy(() => import('@/pages/student/results/MyResultsPage'))
const AdminDashboard = lazy(() => import('@/pages/admin/AdminDashboard'))
const UsersPage = lazy(() => import('@/pages/admin/UsersPage'))
const AuditLogPage = lazy(() => import('@/pages/admin/AuditLogPage'))
const SystemPage = lazy(() => import('@/pages/admin/SystemPage'))

export default function App() {
  return (
    <Suspense fallback={<LoadingState className="min-h-screen" />}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/exam/:slug" element={<PublicExamPage />} />

        <Route element={<GuestOnly />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>

        <Route element={<RequireRole role="teacher" />}>
          <Route path="/teacher" element={<AppLayout />}>
            <Route index element={<TeacherDashboard />} />
            <Route path="courses" element={<CoursesPage />} />
            <Route path="courses/:courseId" element={<CourseDetailPage />} />
            <Route path="exams" element={<ExamsPage />} />
            <Route path="exams/new" element={<CreateExamPage />} />
            <Route path="exams/:examId/:step?" element={<ExamWorkspacePage />} />
            <Route path="submissions" element={<SubmissionsPage />} />
            <Route path="submissions/:submissionId" element={<SubmissionDetailPage />} />
            <Route path="ai-settings" element={<AISettingsPage />} />
            <Route path="evaluation" element={<EvaluationQueuePage />} />
            <Route path="results" element={<ResultsPage />} />
            <Route path="results/:submissionId" element={<ResultDetailPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="profile" element={<ProfilePage />} />
          </Route>
        </Route>

        <Route element={<RequireRole role="student" />}>
          <Route path="/student" element={<AppLayout />}>
            <Route index element={<StudentDashboard />} />
            <Route path="courses" element={<StudentCoursesPage />} />
            <Route path="exams" element={<AvailableExamsPage />} />
            <Route path="exams/:slug" element={<StudentExamPage />} />
            <Route path="submissions" element={<MySubmissionsPage />} />
            <Route path="submissions/:submissionId" element={<SubmissionDetailPage />} />
            <Route path="results" element={<MyResultsPage />} />
            <Route path="results/:submissionId" element={<ResultDetailPage />} />
            <Route path="profile" element={<ProfilePage />} />
          </Route>
        </Route>

        <Route element={<RequireRole role="admin" />}>
          <Route path="/admin" element={<AppLayout />}>
            <Route index element={<AdminDashboard />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="audit" element={<AuditLogPage />} />
            <Route path="system" element={<SystemPage />} />
            <Route path="profile" element={<ProfilePage />} />
          </Route>
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  )
}
