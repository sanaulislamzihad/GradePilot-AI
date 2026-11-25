import { z } from 'zod'

/** Client-side rules mirror the backend; the backend remains the authority. */
export const emailField = z.string().trim().min(1, 'Email is required').pipe(z.email('Enter a valid email address'))

export const passwordField = z
  .string()
  .min(8, 'Use at least 8 characters')
  .max(128, 'Use at most 128 characters')
  .regex(/[A-Za-z]/, 'Include at least one letter')
  .regex(/\d/, 'Include at least one number')

export const optionalText = (max: number) =>
  z.string().trim().max(max, `Use at most ${max} characters`).optional().or(z.literal(''))
