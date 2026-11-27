import { useState } from 'react'
import { PageHeader } from '@/components/ui/PageHeader'
import { ErrorState, LoadingState } from '@/components/ui/States'
import { useAsync } from '@/hooks/useAsync'
import { aiApi } from '@/services/api'
import { ModelSlotsSection } from './ModelSlotsSection'
import { ProvidersSection } from './ProvidersSection'
import { UsageSection } from './UsageSection'

export default function AISettingsPage() {
  const providers = useAsync(aiApi.providers, 'ai-providers')
  const configs = useAsync(aiApi.modelConfigs, 'ai-configs')
  const [usageKey, setUsageKey] = useState(0)

  const loading = (providers.loading && !providers.data) || (configs.loading && !configs.data)
  const error = providers.error ?? configs.error

  return (
    <>
      <PageHeader
        title="AI Settings"
        description="Connect your own provider keys and choose the models that read and mark scripts. AI marks are always suggestions for you to review."
      />
      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState
          message={error}
          onRetry={() => {
            providers.reload()
            configs.reload()
          }}
        />
      ) : providers.data && configs.data ? (
        <div className="space-y-6">
          <ProvidersSection
            providers={providers.data}
            onChange={(updated) => {
              providers.setData((list) => list?.map((p) => (p.slug === updated.slug ? updated : p)) ?? null)
              // Removing a key also clears the slots that used it.
              if (!updated.connection) configs.reload()
            }}
          />
          <ModelSlotsSection
            providers={providers.data}
            configs={configs.data}
            onChange={(slot, config) => {
              configs.setData((list) => {
                const rest = (list ?? []).filter((c) => c.slot !== slot)
                return config ? [...rest, config] : rest
              })
              setUsageKey((k) => k + 1)
            }}
          />
          <UsageSection refreshKey={usageKey} />
        </div>
      ) : null}
    </>
  )
}
