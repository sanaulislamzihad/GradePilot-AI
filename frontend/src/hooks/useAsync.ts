import { useCallback, useEffect, useRef, useState } from 'react'
import { errorMessage } from '@/services/http'

interface AsyncState<T> {
  data: T | null
  error: string | null
  loading: boolean
  reload: () => void
  setData: (updater: (current: T | null) => T | null) => void
}

interface Settled<T> {
  key: string | null
  data: T | null
  error: string | null
}

/**
 * Load data and reload whenever `key` changes (encode the loader's inputs in it,
 * e.g. `courses:${query}:${page}`). Previous data stays visible while the next
 * request runs, and responses for an outdated key are ignored.
 */
export function useAsync<T>(loader: () => Promise<T>, key = ''): AsyncState<T> {
  const [version, setVersion] = useState(0)
  const [settled, setSettled] = useState<Settled<T>>({ key: null, data: null, error: null })
  const loaderRef = useRef(loader)
  const requestKey = `${key}#${version}`

  useEffect(() => {
    loaderRef.current = loader
  })

  useEffect(() => {
    let active = true
    loaderRef.current().then(
      (data) => active && setSettled({ key: requestKey, data, error: null }),
      (err) => active && setSettled((prev) => ({ key: requestKey, data: prev.data, error: errorMessage(err) })),
    )
    return () => {
      active = false
    }
  }, [requestKey])

  const reload = useCallback(() => setVersion((v) => v + 1), [])
  const setData = useCallback(
    (updater: (current: T | null) => T | null) => setSettled((prev) => ({ ...prev, data: updater(prev.data) })),
    [],
  )

  const current = settled.key === requestKey
  return {
    data: settled.data,
    error: current ? settled.error : null,
    loading: !current,
    reload,
    setData,
  }
}
