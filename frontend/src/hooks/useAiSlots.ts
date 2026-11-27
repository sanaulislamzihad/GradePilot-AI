import { useAsync } from '@/hooks/useAsync'
import { aiApi } from '@/services/api'
import type { ModelSlot } from '@/types/api'

/** Which AI model slots the teacher has configured, for showing AI actions only when they can work. */
export function useAiSlots() {
  const { data } = useAsync(aiApi.modelConfigs, 'ai-slots')
  const configured = new Set<ModelSlot>((data ?? []).map((c) => c.slot))
  return { loaded: data !== null, has: (slot: ModelSlot) => configured.has(slot) }
}
