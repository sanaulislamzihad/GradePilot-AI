import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router'
import { z } from 'zod'
import { FormAlert } from '@/components/FormAlert'
import { Button } from '@/components/ui/Button'
import { FormField } from '@/components/ui/FormField'
import { Input } from '@/components/ui/Input'
import { useAuth } from '@/hooks/useAuth'
import { AuthLayout } from '@/layouts/AuthLayout'
import { homePath } from '@/layouts/navigation'
import { errorMessage } from '@/services/http'
import { emailField } from '@/utils/validation'

const schema = z.object({
  email: emailField,
  password: z.string().min(1, 'Password is required'),
})
type LoginValues = z.infer<typeof schema>

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(schema) })

  const onSubmit = async (values: LoginValues) => {
    setServerError(null)
    try {
      const user = await login(values.email, values.password)
      // Return to the page that required sign-in, if it belongs to this role.
      const from = (location.state as { from?: string } | null)?.from
      navigate(from?.startsWith(homePath[user.role]) ? from : homePath[user.role], { replace: true })
    } catch (error) {
      setServerError(errorMessage(error))
    }
  }

  return (
    <AuthLayout
      title="Sign in"
      subtitle={
        <>
          New to GradePilot?{' '}
          <Link to="/register" className="font-medium text-zinc-900 underline underline-offset-4">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <FormAlert message={serverError} />
        <FormField label="Email" error={errors.email?.message}>
          <Input type="email" autoComplete="email" autoFocus {...register('email')} />
        </FormField>
        <FormField label="Password" error={errors.password?.message}>
          <Input type="password" autoComplete="current-password" {...register('password')} />
        </FormField>
        <Button type="submit" className="w-full" loading={isSubmitting}>
          Sign in
        </Button>
      </form>
    </AuthLayout>
  )
}
