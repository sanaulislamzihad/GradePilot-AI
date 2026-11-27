import { Check, Minus, ShieldCheck, X } from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Input, Select } from '@/components/ui/Input'
import { aiApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import type { Capabilities, ModelConfig, ModelInfo, ModelSlot, Provider } from '@/types/api'
import { cn } from '@/utils/cn'
import { formatDateTime } from '@/utils/format'

const SLOTS: { slot: ModelSlot; title: string; description: string; needsVision: boolean }[] = [
  {
    slot: 'ocr',
    title: 'A · OCR and documents',
    description: 'Reads handwriting, scanned scripts and scanned question papers. Needs image support.',
    needsVision: true,
  },
  {
    slot: 'evaluator',
    title: 'B · Evaluator',
    description: 'Marks answers against the rubric, finds evidence and writes feedback. Also drafts model answers and rubrics.',
    needsVision: false,
  },
  {
    slot: 'verifier',
    title: 'C · Verifier',
    description: 'Independently reviews the evaluator’s marks. Choose a different provider or model when you can. Verification runs from the next release.',
    needsVision: false,
  },
]

function Flag({ label, value }: { label: string; value: boolean | null }) {
  const Icon = value === null ? Minus : value ? Check : X
  return (
    <span className={cn('inline-flex items-center gap-1 text-xs', value === false ? 'text-red-700' : 'text-zinc-700')}>
      <Icon className="size-3.5" aria-hidden />
      {label}
      <span className="sr-only">{value === null ? 'unknown' : value ? 'yes' : 'no'}</span>
    </span>
  )
}

function CapabilityResult({ caps, needsVision }: { caps: Capabilities; needsVision: boolean }) {
  const errors = Object.values(caps.errors ?? {})
  return (
    <div className="space-y-1.5 rounded-md bg-zinc-50 px-3 py-2">
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        <Flag label="Listed by provider" value={caps.available} />
        <Flag label="Text" value={caps.text} />
        <Flag label="JSON" value={caps.json} />
        <Flag label="Images" value={caps.vision} />
        {caps.context_window && <span className="text-xs text-zinc-500">{caps.context_window.toLocaleString()} token context</span>}
      </div>
      {needsVision && caps.vision === false && (
        <p className="text-xs text-red-700">This model could not read the test image, so it cannot read scanned scripts.</p>
      )}
      {errors.map((e) => (
        <p key={e} className="text-xs text-red-700">
          {e}
        </p>
      ))}
    </div>
  )
}

interface SlotRowProps {
  slot: (typeof SLOTS)[number]
  config: ModelConfig | undefined
  providers: Provider[]
  onChange: (slot: ModelSlot, config: ModelConfig | null) => void
}

function SlotRow({ slot, config, providers, onChange }: SlotRowProps) {
  const listId = useId()
  const connected = providers.filter((p) => p.connection)
  const [provider, setProvider] = useState(config?.provider ?? connected[0]?.slug ?? '')
  const [model, setModel] = useState(config?.model ?? '')
  const [models, setModels] = useState<ModelInfo[] | null>(null)
  const [modelsError, setModelsError] = useState<string | null>(null)
  const [busy, setBusy] = useState<'save' | 'check' | 'clear' | null>(null)
  const dirty = provider !== (config?.provider ?? '') || model.trim() !== (config?.model ?? '')

  useEffect(() => {
    if (!provider) return
    let active = true
    aiApi
      .models(provider)
      .then((list) => {
        if (!active) return
        setModels(list)
        setModelsError(null)
      })
      .catch((err) => {
        if (!active) return
        setModels([])
        setModelsError(errorMessage(err))
      })
    return () => {
      active = false
    }
  }, [provider])

  const visible = (models ?? []).filter((m) => !slot.needsVision || m.supports_vision !== false)

  const save = async () => {
    setBusy('save')
    try {
      onChange(slot.slot, await aiApi.setModelConfig(slot.slot, provider, model.trim()))
      toast.success(`${slot.title.split(' · ')[1]} model saved. Run a capability check.`)
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  const check = async () => {
    setBusy('check')
    try {
      onChange(slot.slot, await aiApi.checkModelConfig(slot.slot))
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  const clear = async () => {
    setBusy('clear')
    try {
      await aiApi.clearModelConfig(slot.slot)
      onChange(slot.slot, null)
      setModel('')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <li className="space-y-3 px-5 py-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium text-zinc-900">{slot.title}</p>
          <p className="mt-0.5 max-w-2xl text-[13px] text-zinc-500">{slot.description}</p>
        </div>
        {config ? (
          <Badge variant="outline">
            {config.provider_name} · <span className="font-mono">{config.model}</span>
          </Badge>
        ) : (
          <Badge variant="neutral">Not set</Badge>
        )}
      </div>

      {connected.length === 0 ? (
        <p className="text-[13px] text-zinc-500">Connect a provider above first.</p>
      ) : (
        <div className="grid gap-2 sm:grid-cols-[12rem_1fr_auto]">
          <Select
            value={provider}
            onChange={(e) => {
              setProvider(e.target.value)
              setModels(null)
              setModel('')
            }}
            aria-label={`Provider for ${slot.title}`}
          >
            {connected.map((p) => (
              <option key={p.slug} value={p.slug}>
                {p.name}
              </option>
            ))}
          </Select>
          <div>
            <Input
              list={listId}
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder={models === null ? 'Loading models…' : 'Choose or type a model id'}
              aria-label={`Model for ${slot.title}`}
              className="font-mono text-[13px]"
            />
            <datalist id={listId}>
              {visible.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name !== m.id ? m.name : ''}
                  {m.context_window ? ` · ${m.context_window.toLocaleString()} tokens` : ''}
                </option>
              ))}
            </datalist>
            {modelsError && <p className="mt-1 text-xs text-red-700">{modelsError}</p>}
          </div>
          <Button onClick={save} loading={busy === 'save'} disabled={!dirty || !model.trim() || !provider}>
            Save
          </Button>
        </div>
      )}

      {config && (
        <div className="space-y-2">
          {config.capabilities && <CapabilityResult caps={config.capabilities} needsVision={slot.needsVision} />}
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" size="sm" onClick={check} loading={busy === 'check'}>
              <ShieldCheck /> {config.capabilities ? 'Check again' : 'Check capabilities'}
            </Button>
            <Button variant="ghost" size="sm" onClick={clear} loading={busy === 'clear'}>
              Clear
            </Button>
            <span className="text-xs text-zinc-500">
              {config.checked_at ? `Checked ${formatDateTime(config.checked_at)}` : 'Not checked yet'} · sends two tiny test requests
            </span>
          </div>
        </div>
      )}
    </li>
  )
}

interface ModelSlotsSectionProps {
  providers: Provider[]
  configs: ModelConfig[]
  onChange: (slot: ModelSlot, config: ModelConfig | null) => void
}

export function ModelSlotsSection({ providers, configs, onChange }: ModelSlotsSectionProps) {
  const connectedKey = providers.filter((p) => p.connection).map((p) => p.slug).join(',')
  return (
    <Card>
      <CardHeader
        title="Model slots"
        description="Pick a model for each job. The same model can fill more than one slot. Model lists come live from each provider."
      />
      <ul className="divide-y divide-zinc-100">
        {SLOTS.map((slot) => {
          const config = configs.find((c) => c.slot === slot.slot)
          return (
            <SlotRow
              key={`${slot.slot}:${config?.provider ?? ''}:${config?.model ?? ''}:${connectedKey}`}
              slot={slot}
              config={config}
              providers={providers}
              onChange={onChange}
            />
          )
        })}
      </ul>
    </Card>
  )
}
