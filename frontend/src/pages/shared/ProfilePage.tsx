import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'
import { FormAlert } from '@/components/FormAlert'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { FormField } from '@/components/ui/FormField'
import { Input } from '@/components/ui/Input'
import { PageHeader } from '@/components/ui/PageHeader'
import { useAuth } from '@/hooks/useAuth'
import { profileApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import { formatDateTime, roleLabel } from '@/utils/format'
import { optionalText, passwordField } from '@/utils/validation'

const profileSchema = z.object({
  full_name: z.string().trim().min(2, 'Enter your full name').max(120),
  institution: optionalText(160),
  department: optionalText(120),
})
type ProfileValues = z.infer<typeof profileSchema>

const passwordSchema = z
  .object({
    current_password: z.string().min(1, 'Enter your current password'),
    new_password: passwordField,
    confirm_password: z.string(),
  })
  .refine((v) => v.new_password === v.confirm_password, { path: ['confirm_password'], message: 'Passwords do not match' })
type PasswordValues = z.infer<typeof passwordSchema>

function ProfileForm() {
  const { user, updateUser } = useAuth()
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<ProfileValues>({ resolver: zodResolver(profileSchema) })

  useEffect(() => {
    if (user) reset({ full_name: user.full_name, institution: user.institution ?? '', department: user.department ?? '' })
  }, [user, reset])

  const onSubmit = async (values: ProfileValues) => {
    setServerError(null)
    try {
      const updated = await profileApi.update({
        full_name: values.full_name,
        institution: values.institution || null,
        department: values.department || null,
      })
      updateUser(updated)
      toast.success('Profile saved')
    } catch (error) {
      setServerError(errorMessage(error))
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      <FormAlert message={serverError} />
      <FormField label="Full name" error={errors.full_name?.message}>
        <Input autoComplete="name" {...register('full_name')} />
      </FormField>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Institution" optional error={errors.institution?.message}>
          <Input autoComplete="organization" {...register('institution')} />
        </FormField>
        <FormField label="Department" optional error={errors.department?.message}>
          <Input {...register('department')} />
        </FormField>
      </div>
      <div className="flex justify-end">
        <Button type="submit" loading={isSubmitting} disabled={!isDirty}>
          Save profile
        </Button>
      </div>
    </form>
  )
}

function PasswordForm() {
  const { applySession } = useAuth()
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<PasswordValues>({ resolver: zodResolver(passwordSchema) })

  const onSubmit = async (values: PasswordValues) => {
    setServerError(null)
    try {
      applySession(await profileApi.changePassword(values.current_password, values.new_password))
      reset({ current_password: '', new_password: '', confirm_password: '' })
      toast.success('Password changed. Other devices have been signed out.')
    } catch (error) {
      setServerError(errorMessage(error))
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      <FormAlert message={serverError} />
      <FormField label="Current password" error={errors.current_password?.message}>
        <Input type="password" autoComplete="current-password" {...register('current_password')} />
      </FormField>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="New password" error={errors.new_password?.message}>
          <Input type="password" autoComplete="new-password" {...register('new_password')} />
        </FormField>
        <FormField label="Confirm new password" error={errors.confirm_password?.message}>
          <Input type="password" autoComplete="new-password" {...register('confirm_password')} />
        </FormField>
      </div>
      <div className="flex justify-end">
        <Button type="submit" variant="secondary" loading={isSubmitting}>
          Change password
        </Button>
      </div>
    </form>
  )
}

export default function ProfilePage() {
  const { user } = useAuth()
  if (!user) return null

  const details: [string, string][] = [
    ['Email', user.email],
    ['Role', roleLabel[user.role]],
    ...(user.role === 'student' ? ([['Student ID', user.student_id ?? '—']] as [string, string][]) : []),
    ['Member since', formatDateTime(user.created_at)],
    ['Last sign-in', formatDateTime(user.last_login_at)],
  ]

  return (
    <>
      <PageHeader title="Profile" description="Your account details and security settings." />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="h-fit">
          <CardHeader title="Account" action={<Badge variant="solid">{roleLabel[user.role]}</Badge>} />
          <dl className="divide-y divide-zinc-100">
            {details.map(([label, value]) => (
              <div key={label} className="px-5 py-3">
                <dt className="text-xs text-zinc-500">{label}</dt>
                <dd className="mt-0.5 text-sm break-all text-zinc-900">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="border-t border-zinc-100 px-5 py-3 text-xs text-zinc-500">
            Email{user.role === 'student' ? ' and student ID are' : ' is'} fixed after registration.
          </p>
        </Card>

        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader title="Personal information" />
            <CardBody>
              <ProfileForm />
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Password" description="Changing your password signs you out on every other device." />
            <CardBody>
              <PasswordForm />
            </CardBody>
          </Card>
        </div>
      </div>
    </>
  )
}
