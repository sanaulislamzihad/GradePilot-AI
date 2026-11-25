import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { z } from 'zod'
import { FormAlert } from '@/components/FormAlert'
import { Button } from '@/components/ui/Button'
import { FormField } from '@/components/ui/FormField'
import { Input, Select, Textarea } from '@/components/ui/Input'
import { useAsync } from '@/hooks/useAsync'
import { courseApi, type ExamPayload } from '@/services/api'
import { errorMessage, fieldErrors } from '@/services/http'
import type { ExamDetail } from '@/types/api'
import { examTypeLabel, fromLocalInput, hasTwoDecimalsAtMost, toLocalInput } from '@/utils/format'

const FORMAT_OPTIONS = [
  { value: 'pdf', label: 'PDF' },
  { value: 'jpg', label: 'JPG / JPEG' },
  { value: 'png', label: 'PNG' },
]

const schema = z.object({
  title: z.string().trim().min(3, 'Use at least 3 characters').max(200),
  exam_type: z.enum(['quiz', 'assignment', 'midterm', 'final']),
  course_id: z.string(),
  section_id: z.string(),
  exam_date: z.string(),
  submission_deadline: z.string(),
  total_marks: z.coerce
    .number<string>({ error: 'Enter the total marks' })
    .gt(0, 'Total marks must be more than 0')
    .max(1000, 'At most 1000 marks')
    .refine(hasTwoDecimalsAtMost, 'Use at most two decimal places'),
  instructions: z.string().max(5000).optional(),
  allowed_formats: z.array(z.string()).min(1, 'Allow at least one file format'),
  max_file_size_mb: z.coerce.number<string>().int().min(1, 'At least 1 MB').max(50, 'At most 50 MB'),
  max_attempts: z.coerce.number<string>().int().min(1, 'At least 1').max(10, 'At most 10'),
})
type FormInput = z.input<typeof schema>
type FormOutput = z.output<typeof schema>

interface ExamDetailsFormProps {
  exam?: ExamDetail
  submitLabel: string
  disabled?: boolean
  onSubmit: (payload: ExamPayload) => Promise<void>
}

function defaults(exam?: ExamDetail): FormInput {
  return {
    title: exam?.title ?? '',
    exam_type: exam?.exam_type ?? 'quiz',
    course_id: exam?.course_id ?? '',
    section_id: exam?.section_id ?? '',
    exam_date: exam?.exam_date ?? '',
    submission_deadline: toLocalInput(exam?.submission_deadline ?? null),
    total_marks: exam ? String(exam.total_marks) : '',
    instructions: exam?.instructions ?? '',
    allowed_formats: exam ? exam.allowed_formats.filter((f) => f !== 'jpeg') : ['pdf', 'jpg', 'png'],
    max_file_size_mb: String(exam?.max_file_size_mb ?? 20),
    max_attempts: String(exam?.max_attempts ?? 1),
  }
}

export function ExamDetailsForm({ exam, submitLabel, disabled, onSubmit }: ExamDetailsFormProps) {
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    control,
    setValue,
    setError,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<FormInput, unknown, FormOutput>({ resolver: zodResolver(schema), defaultValues: defaults(exam) })

  const courseId = useWatch({ control, name: 'course_id' })
  const formats = useWatch({ control, name: 'allowed_formats' })
  const courses = useAsync(() => courseApi.list({ page_size: 100 }), 'exam-form-courses')
  const course = useAsync(
    () => (courseId ? courseApi.get(courseId) : Promise.resolve(null)),
    `exam-form-course:${courseId}`,
  )

  const toggleFormat = (value: string) => {
    const next = formats.includes(value) ? formats.filter((f) => f !== value) : [...formats, value]
    setValue('allowed_formats', next, { shouldDirty: true, shouldValidate: true })
  }

  const submit = async (values: FormOutput) => {
    setServerError(null)
    try {
      await onSubmit({
        title: values.title,
        exam_type: values.exam_type,
        course_id: values.course_id || null,
        section_id: values.course_id && values.section_id ? values.section_id : null,
        exam_date: values.exam_date || null,
        submission_deadline: fromLocalInput(values.submission_deadline),
        total_marks: values.total_marks,
        instructions: values.instructions?.trim() || null,
        allowed_formats: values.allowed_formats,
        max_file_size_mb: values.max_file_size_mb,
        max_attempts: values.max_attempts,
      })
    } catch (error) {
      const fields = fieldErrors(error)
      Object.entries(fields).forEach(([field, message]) => setError(field as keyof FormInput, { message }))
      setServerError(Object.keys(fields).length ? null : errorMessage(error))
    }
  }

  return (
    <form onSubmit={handleSubmit(submit)} noValidate>
      <fieldset disabled={disabled} className="space-y-6">
        <FormAlert message={serverError} />

        <section className="space-y-4">
          <h3 className="text-sm font-semibold text-zinc-900">Exam information</h3>
          <FormField label="Exam title" error={errors.title?.message}>
            <Input placeholder="CSE445 Midterm Examination" {...register('title')} />
          </FormField>
          <div className="grid gap-4 sm:grid-cols-3">
            <FormField label="Type" error={errors.exam_type?.message}>
              <Select {...register('exam_type')}>
                {Object.entries(examTypeLabel).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label="Total marks" error={errors.total_marks?.message}>
              <Input type="number" inputMode="decimal" step="any" min="0" {...register('total_marks')} />
            </FormField>
            <FormField label="Exam date" optional error={errors.exam_date?.message}>
              <Input type="date" {...register('exam_date')} />
            </FormField>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Course" optional hint={courses.data?.total === 0 ? 'You have no courses yet' : undefined}>
              <Select
                {...register('course_id', {
                  onChange: () => setValue('section_id', '', { shouldDirty: true }),
                })}
              >
                <option value="">No course</option>
                {courses.data?.items.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code} — {c.name}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label="Section" optional error={errors.section_id?.message}>
              <Select {...register('section_id')} disabled={!courseId || !course.data}>
                <option value="">All sections</option>
                {course.data?.sections.map((s) => (
                  <option key={s.id} value={s.id}>
                    Section {s.name}
                  </option>
                ))}
              </Select>
            </FormField>
          </div>
          <FormField label="Instructions" optional error={errors.instructions?.message}>
            <Textarea rows={4} placeholder="Answer all questions. Write your student ID on every page." {...register('instructions')} />
          </FormField>
        </section>

        <section className="space-y-4 border-t border-zinc-200 pt-6">
          <h3 className="text-sm font-semibold text-zinc-900">Submission policy</h3>
          <FormField
            label="Submission deadline"
            error={errors.submission_deadline?.message}
            hint="Required before publishing. Shown in your local time."
          >
            <Input type="datetime-local" {...register('submission_deadline')} />
          </FormField>
          <div>
            <p className="mb-1.5 text-sm font-medium text-zinc-800">Allowed answer script formats</p>
            <div className="flex flex-wrap gap-2">
              {FORMAT_OPTIONS.map((option) => {
                const checked = formats.includes(option.value)
                return (
                  <label
                    key={option.value}
                    className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-sm ${
                      checked ? 'border-zinc-900 text-zinc-900' : 'border-zinc-200 text-zinc-600'
                    }`}
                  >
                    <input type="checkbox" className="accent-zinc-900" checked={checked} onChange={() => toggleFormat(option.value)} />
                    {option.label}
                  </label>
                )
              })}
            </div>
            {errors.allowed_formats && <p className="mt-1.5 text-[13px] text-red-700">{errors.allowed_formats.message}</p>}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Maximum file size (MB)" error={errors.max_file_size_mb?.message}>
              <Input type="number" min="1" max="50" {...register('max_file_size_mb')} />
            </FormField>
            <FormField label="Maximum submission attempts" error={errors.max_attempts?.message}>
              <Input type="number" min="1" max="10" {...register('max_attempts')} />
            </FormField>
          </div>
        </section>

        {!disabled && (
          <div className="flex justify-end border-t border-zinc-200 pt-4">
            <Button type="submit" loading={isSubmitting} disabled={!!exam && !isDirty}>
              {submitLabel}
            </Button>
          </div>
        )}
      </fieldset>
    </form>
  )
}
