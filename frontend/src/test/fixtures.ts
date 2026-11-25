import type { TokenResponse, User, UserRole } from '@/types/api'

export function makeUser(role: UserRole, overrides: Partial<User> = {}): User {
  return {
    id: `${role}-id`,
    email: `${role}@example.edu`,
    full_name: role === 'teacher' ? 'Ada Teacher' : role === 'student' ? 'Sam Student' : 'Root Admin',
    role,
    student_id: role === 'student' ? '2021-001' : null,
    institution: null,
    department: null,
    is_active: true,
    created_at: '2026-11-01T10:00:00Z',
    last_login_at: null,
    ...overrides,
  }
}

export function makeSession(role: UserRole): TokenResponse {
  return { access_token: 'token', token_type: 'bearer', expires_in: 900, user: makeUser(role) }
}
