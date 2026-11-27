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
  submission_count: number
  courses: { id: string; code: string; name: string; section_count: number; student_count: number }[]
  recent_exams: { id: string; title: string; status: ExamStatus; course_code: string | null; submission_deadline: string | null }[]
  recent_activity: ActivityItem[]
}

export interface StudentDashboard {
  enrollment_count: number
  course_count: number
  available_exam_count: number
  submitted_exam_count: number
  upcoming_exams: StudentExamItem[]
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
  submission_count: number
  created_at: string
  updated_at: string
  published_at: string | null
}

export interface ModelAnswer {
  content: string
  source: 'manual' | 'uploaded' | 'ai_generated'
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

// --- Submissions (Phase 3) -------------------------------------------------

export type SubmissionStatus =
  | 'uploaded'
  | 'queued'
  | 'extracting'
  | 'ocr_review_required'
  | 'ready_for_evaluation'
  | 'evaluating'
  | 'verifying'
  | 'teacher_review_required'
  | 'approved'
  | 'published'
  | 'failed'

export interface SubmissionFile {
  id: string
  position: number
  original_filename: string
  content_type: string
  size_bytes: number
  page_count: number
}

export interface SubmissionSummary {
  id: string
  code: string
  exam_id: string
  exam_title: string
  course_code: string | null
  section_name: string | null
  student: { id: string; full_name: string; email: string; student_number: string }
  attempt_number: number
  is_latest: boolean
  status: SubmissionStatus
  status_message: string | null
  file_count: number
  page_count: number
  total_size_bytes: number
  submitted_at: string
}

export interface SubmissionDetail extends SubmissionSummary {
  max_attempts: number
  submission_deadline: string | null
  files: SubmissionFile[]
  /** Teacher-only; null for students. */
  processing_error: string | null
  extraction_notes: string | null
}

export interface StudentExamItem {
  id: string
  slug: string
  title: string
  exam_type: ExamType
  course_code: string | null
  course_name: string | null
  section_name: string | null
  teacher_name: string
  total_marks: number
  submission_deadline: string | null
  is_open: boolean
  max_attempts: number
  attempts_used: number
  latest_submission: {
    id: string
    code: string
    status: SubmissionStatus
    attempt_number: number
    submitted_at: string
  } | null
}

export interface StudentExamDetail extends StudentExamItem {
  exam_date: string | null
  instructions: string | null
  allowed_formats: string[]
  max_file_size_mb: number
  question_count: number
  can_submit: boolean
  blocked_reason: string | null
  attempts_left: number
  submissions: SubmissionSummary[]
}

// --- AI integration (Phase 4) ----------------------------------------------

export type ModelSlot = 'ocr' | 'evaluator' | 'verifier'
export type KeyStatus = 'valid' | 'unverified' | 'invalid'

export interface ProviderConnection {
  id: string
  key_hint: string
  base_url: string | null
  status: KeyStatus
  last_tested_at: string | null
  last_error: string | null
  created_at: string
}

export interface Provider {
  slug: string
  name: string
  requires_base_url: boolean
  connection: ProviderConnection | null
}

export interface ModelInfo {
  id: string
  name: string
  context_window: number | null
  supports_vision: boolean | null
  supports_json: boolean | null
}

export interface Capabilities {
  available: boolean | null
  context_window: number | null
  text: boolean
  json: boolean
  vision: boolean | null
  errors: Record<string, string>
}

export interface ModelConfig {
  slot: ModelSlot
  provider: string
  provider_name: string
  model: string
  capabilities: Capabilities | null
  checked_at: string | null
  updated_at: string
}

export interface UsageEntry {
  id: string
  provider: string
  model: string
  slot: string | null
  task: string
  input_tokens: number | null
  output_tokens: number | null
  cost_usd: number | null
  latency_ms: number
  success: boolean
  error_code: string | null
  created_at: string
}

export interface UsageReport {
  summary: { provider: string; requests: number; failures: number; input_tokens: number; output_tokens: number; cost_usd: number | null }[]
  items: UsageEntry[]
  total: number
  page: number
  page_size: number
}

export type AnswerStatus = 'answered' | 'missing' | 'unreadable'

export interface ExtractedAnswer {
  question_id: string
  label: string
  question_text: string
  max_marks: number | null
  text: string
  status: AnswerStatus
  source: 'pdf_text' | 'ai_ocr' | 'teacher'
  confidence: number
  pages: number[]
  unreadable_notes: string[]
  needs_review: boolean
}

export interface ExtractionView {
  status: SubmissionStatus
  extraction_notes: string | null
  answers: ExtractedAnswer[]
}

export interface EvaluationCriterion {
  id: string
  name: string
  max_marks: number
  awarded: number
  teacher_awarded: number | null
  final_awarded: number
  explanation: string | null
  missing_concepts: string[]
  evidence: { quote: string; found_in_answer: boolean }[]
}

export interface Verification {
  provider: string
  model: string
  same_model_as_evaluator: boolean
  verdict: 'agrees' | 'disagrees' | 'failed'
  suggested_awarded: number | null
  rubric_followed: boolean | null
  evidence_supports_marks: boolean | null
  missed_valid_concepts: string[]
  unsupported_assumptions: string[]
  criterion_notes: { criterion: string; fair: boolean; suggested_awarded: number; note: string }[]
  comment: string | null
}

export interface MathCheck {
  status: 'match' | 'mismatch' | 'uncertain'
  expected: string | null
  student: string | null
  step_errors: { line: number; text: string }[]
  detail: string
}

export interface EvaluationQuestion {
  question_id: string
  label: string
  question_type: QuestionType
  answer_status: AnswerStatus
  awarded: number | null
  teacher_awarded: number | null
  final_awarded: number | null
  max_marks: number
  feedback: string | null
  missing_concepts: string[]
  flags: string[]
  similarity: number | null
  math_check: MathCheck | null
  teacher_comment: string | null
  answer_text: string | null
  criteria: EvaluationCriterion[]
  verification: Verification | null
}

export type ReviewStatus = 'pending' | 'approved' | 'rejected'
export type VerificationStatus = 'pending' | 'completed' | 'skipped' | 'failed'

export interface EvaluationQueueItem {
  evaluation_id: string
  submission_id: string
  submission_code: string
  submission_status: SubmissionStatus
  exam_id: string
  exam_title: string
  student_name: string
  student_number: string
  total_awarded: number | null
  final_total: number | null
  total_max: number
  flags: string[]
  verification_status: VerificationStatus
  review_status: ReviewStatus
  completed_at: string | null
}

export interface HistoryEntry {
  action: string
  summary: string
  actor_name: string | null
  changes: { question: string; field: string; old: string | null; new: string | null }[]
  created_at: string
}

export interface Evaluation {
  id: string
  submission_id: string
  run_number: number
  is_current: boolean
  status: 'completed' | 'failed'
  provider: string
  model: string
  total_awarded: number | null
  total_max: number
  final_total: number | null
  flags: string[]
  started_at: string
  completed_at: string | null
  verification_status: VerificationStatus
  review_status: ReviewStatus
  teacher_comment: string | null
  reviewed_by: string | null
  reviewed_at: string | null
  questions: EvaluationQuestion[]
}
