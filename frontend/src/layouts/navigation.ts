import {
  BookOpen,
  ClipboardList,
  FilePlus2,
  FileText,
  GraduationCap,
  Inbox,
  LayoutDashboard,
  ScrollText,
  Server,
  UserCircle,
  Users,
  type LucideIcon,
} from 'lucide-react'
import type { UserRole } from '@/types/api'

export interface NavItem {
  label: string
  to: string
  icon: LucideIcon
  end?: boolean
  /** A sub-path that has its own menu entry and should not also highlight this one. */
  matchExclude?: string
}

/**
 * Only implemented pages appear here. Modules from later phases (AI evaluation,
 * results, analytics, AI settings) are added to this list when they ship, so no
 * menu entry ever leads to a placeholder.
 */
export const navigation: Record<UserRole, NavItem[]> = {
  teacher: [
    { label: 'Dashboard', to: '/teacher', icon: LayoutDashboard, end: true },
    { label: 'My Exams', to: '/teacher/exams', icon: FileText, matchExclude: '/teacher/exams/new' },
    { label: 'Create Exam', to: '/teacher/exams/new', icon: FilePlus2 },
    { label: 'Submissions', to: '/teacher/submissions', icon: Inbox },
    { label: 'Courses', to: '/teacher/courses', icon: BookOpen },
    { label: 'Profile', to: '/teacher/profile', icon: UserCircle },
  ],
  student: [
    { label: 'Dashboard', to: '/student', icon: LayoutDashboard, end: true },
    { label: 'Available Exams', to: '/student/exams', icon: ClipboardList },
    { label: 'My Submissions', to: '/student/submissions', icon: Inbox },
    { label: 'My Courses', to: '/student/courses', icon: GraduationCap },
    { label: 'Profile', to: '/student/profile', icon: UserCircle },
  ],
  admin: [
    { label: 'Overview', to: '/admin', icon: LayoutDashboard, end: true },
    { label: 'Users', to: '/admin/users', icon: Users },
    { label: 'Audit Log', to: '/admin/audit', icon: ScrollText },
    { label: 'System', to: '/admin/system', icon: Server },
    { label: 'Profile', to: '/admin/profile', icon: UserCircle },
  ],
}

export const homePath: Record<UserRole, string> = {
  teacher: '/teacher',
  student: '/student',
  admin: '/admin',
}

/** Where to go after signing in: back to the page that asked for it, if it belongs to this role. */
export function postLoginPath(role: UserRole, from: unknown): string {
  const home = homePath[role]
  return typeof from === 'string' && (from === home || from.startsWith(`${home}/`)) ? from : home
}
