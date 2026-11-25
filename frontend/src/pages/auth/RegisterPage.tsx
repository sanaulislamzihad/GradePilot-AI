import { zodResolver } from '@hookform/resolvers/zod'
import { GraduationCap, Presentation } from 'lucide-react'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate } from 'react-router'
import { toast } from 'sonner'
import { z } from 'zod'
import { FormAlert } from '@/components/FormAlert'
import { Button } from '@/components/ui/Button'
import { FormField } from '@/components/ui/FormField'
import { Input } from '@/components/ui/Input'
import { useAuth } from '@/hooks/useAuth'
import { AuthLayout } from '@/layouts/AuthLayout'
import { homePath } from '@/layouts/navigation'
import { errorMessage, fieldErrors } from '@/services/http'
import { cn } from '@/utils/cn'
import { emailField, optionalText, passwordField } from '@/utils/validation'

const schema = z
  .object({
    role: z.enum(['teacher', 'student']),
    full_name: z.string().trim().min(2, 'Enter your full name').max(120),
    email: emailField,
    student_id: z.string().trim().max(40).optional(),
    institution: optionalText(160),
    password: passwordField,
    confirm_password: z.string(),
  })
  .superRefine((values, ctx) => {
    if (values.password !== values.confirm_password) {
      ctx.addIssue({ code: 'custom', path: ['confirm_password'], message: 'Passwords do not match' })
    }
    if (values.role === 'student') {
      if (!values.student_id || values.student_id.length < 3) {
        ctx.addIssue({ code: 'custom', path: ['student_id'], message: 'Enter your institution student ID' })
      } else if (!/^[A-Za-z0-9\-_/]+$/.test(values.student_id)) {
        ctx.addIssue({ code: 'custom', path: ['student_id'], message: 'Use letters, numbers, - _ or / only' })
      }
    }
  })
type RegisterValues = z.infer<typeof schema>

const roles = [
  { value: 'teacher', label: 'Teacher', icon: Presentation, hint: 'Create courses and exams' },
  { value: 'student', label: 'Student', icon: GraduationCap, hint: 'Join courses and submit' },
] as const

export default function RegisterPage() {
  const { register: registerAccount } = useAuth()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    setValue,
    setError,
    control,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({ resolver: zodResolver(schema), defaultValues: { role: 'teacher' } })
  const role = useWatch({ control, name: 'role' })

  const onSubmit = async ({ confirm_password: _confirm, ...values }: RegisterValues) => {
    void _confirm
    setServerError(null)
    try {
      const user = await registerAccount({
        ...values,
        student_id: values.role === 'student' ? values.student_id : undefined,
        institution: values.institution || undefined,
      })
      toast.success('Account created. Welcome to GradePilot AI.')
      navigate(homePath[user.role], { replace: true })
    } catch (error) {
      const fields = fieldErrors(error)
      for (const [field, message] of Object.entries(fields)) {
        setError(field as keyof RegisterValues, { message })
      }
      setServerError(Object.keys(fields).length ? null : errorMessage(error))
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle={
        <>
          Already registered?{' '}
          <Link to="/login" className="font-medium text-zinc-900 underline underline-offset-4">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <FormAlert message={serverError} />

        <fieldset>
          <legend className="mb-1.5 text-sm font-medium text-zinc-800">I am a</legend>
          <div className="grid grid-cols-2 gap-2" role="radiogroup">
            {roles.map(({ value, label, icon: Icon, hint }) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={role === value}
                onClick={() => setValue('role', value, { shouldValidate: false })}
                className={cn(
                  'rounded-md border px-3 py-2.5 text-left transition-colors',
                  role === value ? 'border-zinc-900 ring-1 ring-zinc-900' : 'border-zinc-200 hover:border-zinc-300',
                )}
              >
                <span className="flex items-center gap-2 text-sm font-medium text-zinc-900">
                  <Icon className="size-4" aria-hidden />
                  {label}
                </span>
                <span className="mt-0.5 block text-xs text-zinc-500">{hint}</span>
              </button>
            ))}
          </div>
        </fieldset>

        <FormField label="Full name" error={errors.full_name?.message}>
          <Input autoComplete="name" {...register('full_name')} />
        </FormField>
        <FormField label="Email" error={errors.email?.message}>
          <Input type="email" autoComplete="email" {...register('email')} />
        </FormField>
        {role === 'student' && (
          <FormField label="Student ID" error={errors.student_id?.message} hint="As issued by your institution">
            <Input autoComplete="off" {...register('student_id')} />
          </FormField>
        )}
        <FormField label="Institution" optional error={errors.institution?.message}>
          <Input autoComplete="organization" {...register('institution')} />
        </FormField>
        <FormField label="Password" error={errors.password?.message} hint="At least 8 characters with a letter and a number">
          <Input type="password" autoComplete="new-password" {...register('password')} />
        </FormField>
        <FormField label="Confirm password" error={errors.confirm_password?.message}>
          <Input type="password" autoComplete="new-password" {...register('confirm_password')} />
        </FormField>

        <Button type="submit" className="w-full" loading={isSubmitting}>
          Create account
        </Button>
      </form>
    </AuthLayout>
  )
}
