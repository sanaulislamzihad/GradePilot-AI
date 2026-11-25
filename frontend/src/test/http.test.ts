import { describe, expect, it } from 'vitest'
import { errorMessage, fieldErrors } from '@/services/http'

const axiosError = (status: number | null, data?: unknown) =>
  Object.assign(new Error('request failed'), {
    isAxiosError: true,
    response: status === null ? undefined : { status, data },
  })

describe('errorMessage', () => {
  it('uses the API detail when present', () => {
    expect(errorMessage(axiosError(409, { detail: 'Course exists' }))).toBe('Course exists')
  })

  it('explains network failures', () => {
    expect(errorMessage(axiosError(null))).toMatch(/Cannot reach the server/)
  })

  it('hides raw server errors', () => {
    expect(errorMessage(axiosError(500, '<html>Traceback</html>'))).toMatch(/server ran into a problem/)
  })

  it('falls back for unknown errors', () => {
    expect(errorMessage(new Error('boom'), 'Fallback')).toBe('Fallback')
  })
})

describe('fieldErrors', () => {
  it('maps validation errors by field, keeping the first message', () => {
    const error = axiosError(422, {
      detail: 'Some fields are invalid',
      fields: [
        { field: 'password', message: 'Too short' },
        { field: 'password', message: 'Second' },
        { field: 'email', message: 'Invalid email' },
      ],
    })
    expect(fieldErrors(error)).toEqual({ password: 'Too short', email: 'Invalid email' })
  })

  it('ignores non-validation errors', () => {
    expect(fieldErrors(axiosError(400, { detail: 'Bad' }))).toEqual({})
  })
})
