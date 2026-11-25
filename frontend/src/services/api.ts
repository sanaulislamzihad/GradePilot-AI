import { http } from '@/services/http'
import type {
  AdminOverview,
  AuditLogEntry,
  Course,
  CourseDetail,
  EnrolledStudent,
  Page,
  Section,
  StudentDashboard,
  StudentEnrollment,
  SystemStatus,
  TeacherDashboard,
  TokenResponse,
  User,
  UserRole,
} from '@/types/api'

export interface RegisterPayload {
  email: string
  password: string
  full_name: string
  role: 'teacher' | 'student'
  student_id?: string
  institution?: string
  department?: string
}

export interface CoursePayload {
  code: string
  name: string
  description?: string | null
}

const data = <T>(promise: Promise<{ data: T }>) => promise.then((response) => response.data)

export const authApi = {
  login: (email: string, password: string) => data(http.post<TokenResponse>('/auth/login', { email, password })),
  register: (payload: RegisterPayload) => data(http.post<TokenResponse>('/auth/register', payload)),
  logout: () => http.post('/auth/logout'),
  me: () => data(http.get<User>('/auth/me')),
}

export const profileApi = {
  update: (payload: Partial<Pick<User, 'full_name' | 'institution' | 'department'>>) =>
    data(http.patch<User>('/users/me', payload)),
  changePassword: (current_password: string, new_password: string) =>
    data(http.post<TokenResponse>('/users/me/password', { current_password, new_password })),
}

export const courseApi = {
  list: (params: { q?: string; page?: number; page_size?: number } = {}) =>
    data(http.get<Page<Course>>('/courses', { params })),
  get: (id: string) => data(http.get<CourseDetail>(`/courses/${id}`)),
  create: (payload: CoursePayload) => data(http.post<CourseDetail>('/courses', payload)),
  update: (id: string, payload: CoursePayload) => data(http.put<CourseDetail>(`/courses/${id}`, payload)),
  remove: (id: string) => http.delete(`/courses/${id}`),
  createSection: (courseId: string, name: string) =>
    data(http.post<Section>(`/courses/${courseId}/sections`, { name })),
  updateSection: (id: string, payload: { name?: string; is_open?: boolean }) =>
    data(http.patch<Section>(`/sections/${id}`, payload)),
  removeSection: (id: string) => http.delete(`/sections/${id}`),
  regenerateCode: (id: string) => data(http.post<Section>(`/sections/${id}/join-code`)),
  students: (sectionId: string) => data(http.get<EnrolledStudent[]>(`/sections/${sectionId}/students`)),
  removeStudent: (sectionId: string, enrollmentId: string) =>
    http.delete(`/sections/${sectionId}/students/${enrollmentId}`),
}

export const studentApi = {
  enrollments: () => data(http.get<StudentEnrollment[]>('/student/enrollments')),
  join: (join_code: string) => data(http.post<StudentEnrollment>('/student/enrollments', { join_code })),
  leave: (enrollmentId: string) => http.delete(`/student/enrollments/${enrollmentId}`),
}

export const dashboardApi = {
  teacher: () => data(http.get<TeacherDashboard>('/dashboard/teacher')),
  student: () => data(http.get<StudentDashboard>('/dashboard/student')),
}

export interface UserFilters {
  q?: string
  role?: UserRole
  is_active?: boolean
  page?: number
  page_size?: number
}

export const adminApi = {
  overview: () => data(http.get<AdminOverview>('/admin/overview')),
  users: (params: UserFilters) => data(http.get<Page<User>>('/admin/users', { params })),
  updateUser: (id: string, payload: { role?: UserRole; is_active?: boolean }) =>
    data(http.patch<User>(`/admin/users/${id}`, payload)),
  auditLogs: (params: { action?: string; page?: number; page_size?: number }) =>
    data(http.get<Page<AuditLogEntry>>('/admin/audit-logs', { params })),
  system: () => data(http.get<SystemStatus>('/admin/system')),
}
