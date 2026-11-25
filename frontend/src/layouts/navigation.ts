import {
  BookOpen,
  GraduationCap,
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
}

/**
 * Only implemented pages appear here. Modules from later phases (exams,
 * submissions, evaluation, results, analytics, AI settings) are added to this
 * list when they ship, so no menu entry ever leads to a placeholder.
 */
export const navigation: Record<UserRole, NavItem[]> = {
  teacher: [
    { label: 'Dashboard', to: '/teacher', icon: LayoutDashboard, end: true },
    { label: 'Courses', to: '/teacher/courses', icon: BookOpen },
    { label: 'Profile', to: '/teacher/profile', icon: UserCircle },
  ],
  student: [
    { label: 'Dashboard', to: '/student', icon: LayoutDashboard, end: true },
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
