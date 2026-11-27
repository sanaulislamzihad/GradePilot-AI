import { useEffect } from 'react'
import { useSearchParams } from 'react-router'
import { useAsync } from '@/hooks/useAsync'
import { examApi } from '@/services/api'

/**
 * The exam chosen with `?exam=` on the results and analytics pages. Without one,
 * the most recent exam that has submissions is selected.
 */
export function useExamParam() {
  const [params, setParams] = useSearchParams()
  const examId = params.get('exam') ?? ''
  const exams = useAsync(() => examApi.list({ page_size: 100 }), 'results-exams')
  const withSubmissions = exams.data?.items.filter((e) => e.submission_count > 0) ?? []

  const firstId = withSubmissions[0]?.id
  useEffect(() => {
    if (!examId && firstId) setParams({ exam: firstId }, { replace: true })
  }, [examId, firstId, setParams])

  return {
    examId,
    exams: withSubmissions,
    loading: exams.loading && !exams.data,
    error: exams.error,
    select: (id: string) => setParams(id ? { exam: id } : {}, { replace: true }),
  }
}
