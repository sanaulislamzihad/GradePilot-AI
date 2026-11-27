import { useEffect } from 'react'

/** Call `tick` every `intervalMs` while `active` is true (e.g. while a job is running). */
export function usePolling(active: boolean, tick: () => void, intervalMs = 3000) {
  useEffect(() => {
    if (!active) return
    const timer = setInterval(tick, intervalMs)
    return () => clearInterval(timer)
  }, [active, tick, intervalMs])
}
