import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { authApi, type RegisterPayload } from '@/services/api'
import { bindSessionListener, refreshSession, setAccessToken } from '@/services/http'
import type { TokenResponse, User } from '@/types/api'

type AuthStatus = 'loading' | 'authenticated' | 'anonymous'

export interface AuthContextValue {
  status: AuthStatus
  user: User | null
  login: (email: string, password: string) => Promise<User>
  register: (payload: RegisterPayload) => Promise<User>
  logout: () => Promise<void>
  /** Apply a fresh session returned by the API (e.g. after a password change). */
  applySession: (session: TokenResponse) => void
  updateUser: (user: User) => void
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [user, setUser] = useState<User | null>(null)

  const applySession = useCallback((session: TokenResponse | null) => {
    setAccessToken(session?.access_token ?? null)
    setUser(session?.user ?? null)
    setStatus(session ? 'authenticated' : 'anonymous')
  }, [])

  useEffect(() => {
    bindSessionListener(applySession)
    // Restore the session from the refresh cookie, if there is one.
    refreshSession().then(applySession, () => applySession(null))
    return () => bindSessionListener(null)
  }, [applySession])

  const login = useCallback(
    async (email: string, password: string) => {
      const session = await authApi.login(email, password)
      applySession(session)
      return session.user
    },
    [applySession],
  )

  const register = useCallback(
    async (payload: RegisterPayload) => {
      const session = await authApi.register(payload)
      applySession(session)
      return session.user
    },
    [applySession],
  )

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } finally {
      applySession(null)
    }
  }, [applySession])

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, login, register, logout, applySession, updateUser: setUser }),
    [status, user, login, register, logout, applySession],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
