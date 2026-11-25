import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { FormAlert } from '@/components/FormAlert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { FormField } from '@/components/ui/FormField'
import { Input, Textarea } from '@/components/ui/Input'
import type { CoursePayload } from '@/services/api'
import { errorMessage, fieldErrors } from '@/services/http'
import type { Course } from '@/types/api'

const schema = z.object({
  code: z
    .string()
    .trim()
    .min(2, 'Enter a course code')
    .max(30)
    .regex(/^[A-Za-z0-9\-\s]+$/, 'Use letters, numbers, spaces or hyphens'),
  name: z.string().trim().min(2, 'Enter a course name').max(160),
  description: z.string().trim().max(2000).optional(),
})
type CourseValues = z.infer<typeof schema>

interface CourseFormProps {
  course?: Course
  onSubmit: (payload: CoursePayload) => Promise<void>
  onDone: () => void
  onBusyChange: (busy: boolean) => void
}

/** Mounted fresh each time the dialog opens, so it always starts from the current course. */
function CourseForm({ course, onSubmit, onDone, onBusyChange }: CourseFormProps) {
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<CourseValues>({
    resolver: zodResolver(schema),
    defaultValues: { code: course?.code ?? '', name: course?.name ?? '', description: course?.description ?? '' },
  })

  const submit = async (values: CourseValues) => {
    setServerError(null)
    onBusyChange(true)
    try {
      await onSubmit({ ...values, description: values.description || null })
      onDone()
    } catch (error) {
      const fields = fieldErrors(error)
      Object.entries(fields).forEach(([field, message]) => setError(field as keyof CourseValues, { message }))
      setServerError(Object.keys(fields).length ? null : errorMessage(error))
    } finally {
      onBusyChange(false)
    }
  }

  return (
    <form onSubmit={handleSubmit(submit)} noValidate className="space-y-4">
      <FormAlert message={serverError} />
      <div className="grid gap-4 sm:grid-cols-[9rem_1fr]">
        <FormField label="Code" error={errors.code?.message}>
          <Input placeholder="CSE445" className="uppercase" autoFocus {...register('code')} />
        </FormField>
        <FormField label="Name" error={errors.name?.message}>
          <Input placeholder="Machine Learning" {...register('name')} />
        </FormField>
      </div>
      <FormField label="Description" optional error={errors.description?.message}>
        <Textarea rows={3} {...register('description')} />
      </FormField>
      <div className="-mx-5 flex justify-end gap-2 border-t border-zinc-200 px-5 pt-3">
        <Button variant="secondary" onClick={onDone} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button type="submit" loading={isSubmitting}>
          {course ? 'Save changes' : 'Create course'}
        </Button>
      </div>
    </form>
  )
}

interface CourseFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  course?: Course
  onSubmit: (payload: CoursePayload) => Promise<void>
}

export function CourseFormDialog({ open, onOpenChange, course, onSubmit }: CourseFormDialogProps) {
  const [busy, setBusy] = useState(false)
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => !busy && onOpenChange(next)}
      title={course ? 'Edit course' : 'New course'}
      description={course ? undefined : 'You can add sections after creating the course.'}
    >
      <CourseForm course={course} onSubmit={onSubmit} onDone={() => onOpenChange(false)} onBusyChange={setBusy} />
    </Dialog>
  )
}
