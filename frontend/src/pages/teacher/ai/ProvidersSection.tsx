import { KeyRound, Lock, RefreshCw, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { FormAlert } from '@/components/FormAlert'
import { StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/Dialog'
import { FormField } from '@/components/ui/FormField'
import { Input } from '@/components/ui/Input'
import { aiApi } from '@/services/api'
import { errorMessage } from '@/services/http'
import type { Provider } from '@/types/api'
import { formatDateTime } from '@/utils/format'

const statusTone = { valid: 'positive', unverified: 'warning', invalid: 'negative' } as const
const statusLabel = { valid: 'Connected', unverified: 'Saved, not verified', invalid: 'Key rejected' } as const

function ConnectForm({ provider, onDone, onCancel }: { provider: Provider; onDone: (p: Provider) => void; onCancel: () => void }) {
  const [key, setKey] = useState('')
  const [baseUrl, setBaseUrl] = useState(provider.connection?.base_url ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const updated = await aiApi.connect(provider.slug, key, provider.requires_base_url ? baseUrl : undefined)
      setKey('')
      onDone(updated)
      toast.success(
        updated.connection?.status === 'valid'
          ? `${provider.name} connected`
          : `${provider.name} key saved, but it could not be verified yet`,
      )
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 border-t border-zinc-100 px-5 py-4" autoComplete="off">
      <FormAlert message={error} />
      {provider.requires_base_url && (
        <FormField label="Base URL" hint="An OpenAI-compatible server, for example http://localhost:11434/v1">
          <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="http://localhost:11434/v1" />
        </FormField>
      )}
      <FormField label="API key" hint="The key is tested, then stored encrypted. It is never shown again.">
        <Input
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          autoComplete="new-password"
          spellCheck={false}
          placeholder="Paste your API key"
        />
      </FormField>
      <div className="flex justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
        <Button type="submit" size="sm" loading={busy} disabled={key.trim().length < 8}>
          Test and save
        </Button>
      </div>
    </form>
  )
}

function ProviderRow({ provider, onChange }: { provider: Provider; onChange: (p: Provider | null) => void }) {
  const [editing, setEditing] = useState(false)
  const [testing, setTesting] = useState(false)
  const [removing, setRemoving] = useState(false)
  const connection = provider.connection

  const test = async () => {
    setTesting(true)
    try {
      const updated = await aiApi.test(provider.slug)
      onChange(updated)
      const status = updated.connection?.status
      if (status === 'valid') toast.success(`${provider.name} key works`)
      else toast.error(updated.connection?.last_error ?? 'The key could not be verified')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setTesting(false)
    }
  }

  return (
    <li>
      <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-medium text-zinc-900">{provider.name}</p>
          {connection ? (
            <p className="mt-0.5 text-xs text-zinc-500">
              Key <span className="font-mono">{connection.key_hint}</span>
              {connection.base_url && <> · {connection.base_url}</>} · tested {formatDateTime(connection.last_tested_at)}
            </p>
          ) : (
            <p className="mt-0.5 text-xs text-zinc-500">Not connected</p>
          )}
          {connection?.last_error && <p className="mt-1 text-xs text-red-700">{connection.last_error}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {connection && <StatusBadge tone={statusTone[connection.status]}>{statusLabel[connection.status]}</StatusBadge>}
          {connection ? (
            <>
              <Button variant="ghost" size="icon" onClick={test} loading={testing} aria-label={`Test ${provider.name} key`} title="Test the key">
                {!testing && <RefreshCw />}
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setEditing((v) => !v)}>
                Replace key
              </Button>
              <Button variant="ghost" size="icon" onClick={() => setRemoving(true)} aria-label={`Remove ${provider.name} key`}>
                <Trash2 />
              </Button>
            </>
          ) : (
            !editing && (
              <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
                <KeyRound /> Connect
              </Button>
            )
          )}
        </div>
      </div>
      {editing && (
        <ConnectForm
          provider={provider}
          onCancel={() => setEditing(false)}
          onDone={(updated) => {
            setEditing(false)
            onChange(updated)
          }}
        />
      )}
      <ConfirmDialog
        open={removing}
        onOpenChange={setRemoving}
        title={`Remove the ${provider.name} key?`}
        description="The encrypted key is deleted, and any model slot using this provider is cleared."
        confirmLabel="Remove key"
        destructive
        onConfirm={async () => {
          if (!connection) return
          await aiApi.removeProvider(connection.id)
          onChange({ ...provider, connection: null })
          toast.success(`${provider.name} key removed`)
        }}
      />
    </li>
  )
}

export function ProvidersSection({ providers, onChange }: { providers: Provider[]; onChange: (p: Provider) => void }) {
  return (
    <Card>
      <CardHeader
        title="Provider keys"
        description="Bring your own API keys. Connect only the providers you use; one key covers every model of that provider."
      />
      <ul className="divide-y divide-zinc-100">
        {providers.map((provider) => (
          <ProviderRow key={provider.slug} provider={provider} onChange={(p) => onChange(p ?? { ...provider, connection: null })} />
        ))}
      </ul>
      <p className="flex items-start gap-2 border-t border-zinc-100 px-5 py-3 text-xs text-zinc-500">
        <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        Keys are encrypted on the server (AES-256-GCM), used only for your own requests, and never sent back to the
        browser. A free tier from a provider still needs an API key; a chat subscription does not include API usage.
      </p>
    </Card>
  )
}
