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
  exam_count: number
  published_exam_count: number
  draft_exam_count: number
  courses: { id: string; code: string; name: string; section_count: number; student_count: number }[]
  recent_exams: { id: string; title: string; status: ExamStatus; course_code: string | null; submission_deadline: string | null }[]
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

// --- Exams (Phase 2) -------------------------------------------------------

export type ExamType = 'quiz' | 'assignment' | 'midterm' | 'final'
export type ExamStatus = 'draft' | 'published'
export type QuestionType = 'short' | 'descriptive' | 'mathematical' | 'multiple_choice'
export type ExtractionStatus = 'succeeded' | 'needs_ocr' | 'failed'

export interface ExamSummary {
  id: string
  title: string
  exam_type: ExamType
  status: ExamStatus
  course_id: string | null
  course_code: string | null
  course_name: string | null
  section_id: string | null
  section_name: string | null
  total_marks: number
  exam_date: string | null
  submission_deadline: string | null
  question_count: number
  created_at: string
  updated_at: string
  published_at: string | null
}

export interface ModelAnswer {
  content: string
  source: 'manual' | 'uploaded'
  is_approved: boolean
  approved_at: string | null
  updated_at: string
}

export interface RubricCriterion {
  id: string
  name: string
  description: string | null
  max_marks: number
}

export interface Rubric {
  is_approved: boolean
  approved_at: string | null
  total: number
  criteria: RubricCriterion[]
}

export interface Question {
  id: string
  parent_id: string | null
  label: string
  full_label: string
  position: number
  text: string
  question_type: QuestionType
  marks: number | null
  is_leaf: boolean
  model_answer: ModelAnswer | null
  rubric: Rubric | null
  children: Question[]
}

export interface ExamDocument {
  id: string
  kind: 'question_paper' | 'model_answer'
  original_filename: string
  content_type: string
  size_bytes: number
  page_count: number | null
  extraction_status: ExtractionStatus
  extraction_message: string | null
  extracted_text: string | null
  created_at: string
}

export interface ReadinessCheck {
  key: 'details' | 'questions' | 'marks' | 'model_answers' | 'rubrics'
  label: string
  ok: boolean
  detail: string
}

export interface ExamDetail extends ExamSummary {
  instructions: string | null
  allowed_formats: string[]
  max_file_size_mb: number
  max_attempts: number
  public_slug: string | null
  questions: Question[]
  documents: ExamDocument[]
  readiness: {
    ready: boolean
    allocated_marks: number
    total_marks: number
    checks: ReadinessCheck[]
  }
}

export interface ModelAnswerUploadResult {
  document: ExamDocument
  matched: string[]
  skipped_approved: string[]
  unmatched_questions: string[]
  unused_sections: string[]
  exam: ExamDetail
}

export interface PublicExam {
  title: string
  exam_type: ExamType
  course_code: string | null
  course_name: string | null
  section_name: string | null
  teacher_name: string
  total_marks: number
  exam_date: string | null
  submission_deadline: string | null
  instructions: string | null
  allowed_formats: string[]
  max_file_size_mb: number
  max_attempts: number
  question_count: number
  is_open: boolean
}
