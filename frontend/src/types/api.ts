/** Types mirroring the FastAPI response schemas (backend/app/schemas). */

export type UserRole = 'admin' | 'teacher' | 'student'

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  student_id: string | null
  institution: string | null
  department: string | null
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: User
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface Section {
  id: string
  course_id: string
  name: string
  join_code: string
  is_open: boolean
  student_count: number
  created_at: string
}

export interface Course {
  id: string
  code: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
  section_count: number
  student_count: number
}

export interface CourseDetail extends Course {
  sections: Section[]
}

export interface EnrolledStudent {
  enrollment_id: string
  user_id: string
  full_name: string
  email: string
  student_id: string | null
  joined_at: string
}

export interface StudentEnrollment {
  enrollment_id: string
  section_id: string
  section_name: string
  course_id: string
  course_code: string
  course_name: string
  teacher_name: string
  joined_at: string
}

export interface ActivityItem {
  id: string
  action: string
  summary: string
  created_at: string
}

export interface TeacherDashboard {
  course_count: number
  section_count: number
  student_count: number
  courses: { id: string; code: string; name: string; section_count: number; student_count: number }[]
  recent_activity: ActivityItem[]
}

export interface StudentDashboard {
  enrollment_count: number
  course_count: number
  enrollments: StudentEnrollment[]
  recent_activity: ActivityItem[]
}

export interface AdminOverview {
  total_users: number
  active_users: number
  users_by_role: Record<UserRole, number>
  course_count: number
  section_count: number
  enrollment_count: number
  new_users_last_7_days: number
}

export interface AuditLogEntry {
  id: string
  action: string
  summary: string
  actor_name: string | null
  actor_email: string | null
  entity_type: string | null
  entity_id: string | null
  ip_address: string | null
  created_at: string
}

export interface SystemStatus {
  status: 'ok' | 'degraded'
  version: string
  environment: string
  database_backend: string
  database_ok: boolean
  migration_revision: string | null
  uptime_seconds: number
  storage_writable: boolean
  active_sessions: number
}

export interface ApiErrorBody {
  detail: string
  fields?: { field: string | null; message: string }[]
}
