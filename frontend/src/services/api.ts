import { http } from '@/services/http'
import type {
  AdminOverview,
  AuditLogEntry,
  Course,
  CourseDetail,
  EnrolledStudent,
  ExamDetail,
  ExamSummary,
  ExamStatus,
  ExamType,
  Evaluation,
  ExtractionView,
  ModelAnswerUploadResult,
  ModelConfig,
  ModelInfo,
  ModelSlot,
  Provider,
  UsageReport,
  AnswerStatus,
  Page,
  PublicExam,
  QuestionType,
  Section,
  StudentDashboard,
  StudentEnrollment,
  StudentExamDetail,
  StudentExamItem,
  SubmissionDetail,
  SubmissionStatus,
  SubmissionSummary,
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
  exams: () => data(http.get<StudentExamItem[]>('/student/exams')),
  exam: (slug: string) => data(http.get<StudentExamDetail>(`/student/exams/${slug}`)),
  submit: (examId: string, files: File[], idempotencyKey: string, onProgress?: (fraction: number) => void) => {
    const form = new FormData()
    files.forEach((file) => form.append('files', file))
    return data(
      http.post<SubmissionDetail>(`/exams/${examId}/submissions`, form, {
        headers: { 'Idempotency-Key': idempotencyKey },
        timeout: 300_000,
        onUploadProgress: (event) => event.total && onProgress?.(event.loaded / event.total),
      }),
    )
  },
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

export interface ExamPayload {
  title: string
  exam_type: ExamType
  course_id: string | null
  section_id: string | null
  exam_date: string | null
  submission_deadline: string | null
  total_marks: number
  instructions: string | null
  allowed_formats: string[]
  max_file_size_mb: number
  max_attempts: number
}

export interface QuestionPayload {
  label?: string
  text?: string
  question_type?: QuestionType
  marks?: number | null
  clear_marks?: boolean
}

export interface CriterionPayload {
  name: string
  description: string | null
  max_marks: number
}

const upload = (url: string, file: File, params?: Record<string, unknown>) => {
  const form = new FormData()
  form.append('file', file)
  return http.post(url, form, { params, timeout: 120_000 })
}

export const examApi = {
  list: (params: { q?: string; status?: ExamStatus; page?: number; page_size?: number } = {}) =>
    data(http.get<Page<ExamSummary>>('/exams', { params })),
  get: (id: string) => data(http.get<ExamDetail>(`/exams/${id}`)),
  create: (payload: ExamPayload) => data(http.post<ExamDetail>('/exams', payload)),
  update: (id: string, payload: ExamPayload) => data(http.put<ExamDetail>(`/exams/${id}`, payload)),
  remove: (id: string) => http.delete(`/exams/${id}`),

  uploadQuestionPaper: (id: string, file: File) =>
    upload(`/exams/${id}/upload-question-paper`, file).then((r) => r.data as ExamDetail),
  extractQuestions: (id: string, replace: boolean) =>
    data(http.post<{ created: number; with_marks: number; exam: ExamDetail }>(`/exams/${id}/extract-questions`, { replace })),
  downloadDocument: (examId: string, documentId: string) =>
    http.get<Blob>(`/exams/${examId}/documents/${documentId}`, { responseType: 'blob' }).then((r) => r.data),
  removeDocument: (examId: string, documentId: string) =>
    data(http.delete<ExamDetail>(`/exams/${examId}/documents/${documentId}`)),

  addQuestion: (examId: string, payload: QuestionPayload & { parent_id?: string | null }) =>
    data(http.post<ExamDetail>(`/exams/${examId}/questions`, payload)),
  updateQuestion: (questionId: string, payload: QuestionPayload) =>
    data(http.patch<ExamDetail>(`/questions/${questionId}`, payload)),
  removeQuestion: (questionId: string) => data(http.delete<ExamDetail>(`/questions/${questionId}`)),
  reorder: (examId: string, parentId: string | null, orderedIds: string[]) =>
    data(http.post<ExamDetail>(`/exams/${examId}/questions/reorder`, { parent_id: parentId, ordered_ids: orderedIds })),
  saveMarks: (examId: string, items: { question_id: string; marks: number | null }[]) =>
    data(http.put<ExamDetail>(`/exams/${examId}/marks`, { items })),

  saveModelAnswer: (questionId: string, content: string, approved: boolean) =>
    data(http.put<ExamDetail>(`/questions/${questionId}/model-answer`, { content, approved })),
  removeModelAnswer: (questionId: string) => data(http.delete<ExamDetail>(`/questions/${questionId}/model-answer`)),
  uploadModelAnswers: (examId: string, file: File, overwriteApproved: boolean) =>
    upload(`/exams/${examId}/model-answer`, file, { overwrite_approved: overwriteApproved }).then(
      (r) => r.data as ModelAnswerUploadResult,
    ),

  saveRubric: (questionId: string, criteria: CriterionPayload[], approved: boolean) =>
    data(http.put<ExamDetail>(`/questions/${questionId}/rubric`, { criteria, approved })),
  removeRubric: (questionId: string) => data(http.delete<ExamDetail>(`/questions/${questionId}/rubric`)),

  readPaperWithAi: (id: string) => data(http.post<ExamDetail>(`/exams/${id}/ocr-question-paper`, undefined, { timeout: 300_000 })),
  draftModelAnswer: (questionId: string) =>
    data(http.post<ExamDetail>(`/questions/${questionId}/model-answer/generate`, undefined, { timeout: 180_000 })),
  suggestRubric: (questionId: string) =>
    data(http.post<ExamDetail>(`/questions/${questionId}/rubric/suggest`, undefined, { timeout: 180_000 })),
  publish: (id: string) => data(http.post<ExamDetail>(`/exams/${id}/publish`)),
  unpublish: (id: string) => data(http.post<ExamDetail>(`/exams/${id}/unpublish`)),
}

export const publicApi = {
  exam: (slug: string) => data(http.get<PublicExam>(`/public/exams/${slug}`)),
}

export const submissionApi = {
  list: (params: { exam_id?: string; status?: SubmissionStatus; q?: string; latest_only?: boolean; page?: number; page_size?: number } = {}) =>
    data(http.get<Page<SubmissionSummary>>('/submissions', { params })),
  get: (id: string) => data(http.get<SubmissionDetail>(`/submissions/${id}`)),
  downloadFile: (id: string, fileId: string) =>
    http.get<Blob>(`/submissions/${id}/files/${fileId}`, { responseType: 'blob' }).then((r) => r.data),
}

export const aiApi = {
  providers: () => data(http.get<Provider[]>('/providers')),
  connect: (provider: string, api_key: string, base_url?: string) =>
    data(http.post<Provider>('/providers/connect', { provider, api_key, base_url: base_url || null }, { timeout: 60_000 })),
  test: (provider: string) => data(http.post<Provider>('/providers/test', { provider }, { timeout: 60_000 })),
  models: (provider: string) => data(http.get<ModelInfo[]>('/providers/models', { params: { provider }, timeout: 60_000 })),
  removeProvider: (connectionId: string) => http.delete(`/providers/${connectionId}`),
  modelConfigs: () => data(http.get<ModelConfig[]>('/model-configs')),
  setModelConfig: (slot: ModelSlot, provider: string, model: string) =>
    data(http.put<ModelConfig>(`/model-configs/${slot}`, { provider, model })),
  clearModelConfig: (slot: ModelSlot) => http.delete(`/model-configs/${slot}`),
  checkModelConfig: (slot: ModelSlot) => data(http.post<ModelConfig>(`/model-configs/${slot}/check`, undefined, { timeout: 180_000 })),
  usage: (page: number, page_size = 20) => data(http.get<UsageReport>('/usage', { params: { page, page_size } })),
}

export const processingApi = {
  extract: (id: string) => data(http.post<SubmissionDetail>(`/submissions/${id}/extract`, undefined, { timeout: 300_000 })),
  retry: (id: string) => data(http.post<SubmissionDetail>(`/submissions/${id}/retry`, undefined, { timeout: 300_000 })),
  evaluate: (id: string) => data(http.post<SubmissionDetail>(`/submissions/${id}/evaluate`, undefined, { timeout: 300_000 })),
  processPending: (examId: string) =>
    data(http.post<{ queued: number; skipped: number }>(`/exams/${examId}/process-pending`, undefined, { timeout: 300_000 })),
  extractedAnswers: (id: string) => data(http.get<ExtractionView>(`/submissions/${id}/extracted-answers`)),
  correctAnswers: (id: string, answers: { question_id: string; text: string; status: AnswerStatus }[], confirm: boolean) =>
    data(http.put<ExtractionView>(`/submissions/${id}/extracted-answers`, { answers, confirm })),
  evaluation: (id: string) => data(http.get<Evaluation>(`/submissions/${id}/evaluation`)),
}
