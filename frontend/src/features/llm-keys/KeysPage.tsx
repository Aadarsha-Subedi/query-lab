import { Delete02Icon, Key01Icon } from '@hugeicons/core-free-icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { errorText } from '@/lib/api/error-text'
import { cn } from '@/lib/utils'

import {
  activateKey,
  changeModel,
  keysQuery,
  modelsQuery,
  removeKey,
  saveKey,
  setSource,
  settingsQuery,
  type AiSource,
  type SavedKey,
} from './api'
import { ProviderLogo } from './ProviderLogo'
import { PROVIDER_LABEL, PROVIDER_ORDER, type ProviderName } from './providers'

/** Everything that depends on the saved keys or the chosen source. */
function useRefresh() {
  const queryClient = useQueryClient()
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['llm-keys'] }),
      queryClient.invalidateQueries({ queryKey: ['llm-settings'] }),
      queryClient.invalidateQueries({ queryKey: ['agent-limits'] }),
    ])
  }
}

const SOURCE_OPTIONS: { value: AiSource; title: string; text: string }[] = [
  {
    value: 'querylab',
    title: 'QueryLab AI',
    text: 'Nothing to set up. Uses our shared key, which has a daily limit for everyone.',
  },
  {
    value: 'own',
    title: 'My own AI',
    text: 'Use your own OpenAI or Gemini key. Your questions no longer count against our daily limit.',
  },
]

function SourceChoice({ source }: { source: AiSource }) {
  const refresh = useRefresh()
  const mutation = useMutation({ mutationFn: setSource, onSuccess: refresh })
  const failure = mutation.isError ? errorText(mutation.error) : null
  return (
    <fieldset className="flex flex-col gap-3" disabled={mutation.isPending}>
      <legend className="mb-3 text-body font-medium">Which AI answers your questions?</legend>
      <div className="grid gap-3 sm:grid-cols-2">
        {SOURCE_OPTIONS.map((option) => (
          <label
            key={option.value}
            className={cn(
              'flex cursor-pointer items-start gap-3 rounded-lg border bg-surface p-4 transition-colors duration-fast has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring has-[:focus-visible]:ring-offset-2 has-[:focus-visible]:ring-offset-background',
              source === option.value && 'border-primary bg-surface-muted',
            )}
          >
            <input
              type="radio"
              name="ai-source"
              value={option.value}
              checked={source === option.value}
              onChange={() => {
                mutation.mutate(option.value)
              }}
              className="mt-1 size-4 accent-primary"
            />
            <span className="flex flex-col gap-1">
              <span className="text-body font-medium">{option.title}</span>
              <span className="text-small text-muted-foreground">{option.text}</span>
            </span>
          </label>
        ))}
      </div>
      {failure && (
        <p role="alert" className="text-small text-danger-foreground">
          {failure.message} {failure.hint}
        </p>
      )}
    </fieldset>
  )
}

function ModelSelect({
  provider,
  value,
  models,
  onChange,
  disabled,
  label,
}: {
  provider: ProviderName
  value: string
  models: string[]
  onChange: (model: string) => void
  disabled?: boolean
  label: string
}) {
  // A saved model that is no longer on the list stays visible instead of vanishing.
  const options = models.includes(value) || value === '' ? models : [value, ...models]
  return (
    <Select value={value} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger aria-label={label} className="min-w-44" data-provider={provider}>
        <SelectValue placeholder="Choose a model" />
      </SelectTrigger>
      <SelectContent>
        {options.map((model) => (
          <SelectItem key={model} value={model}>
            {model}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function KeyRow({
  provider,
  saved,
  models,
}: {
  provider: ProviderName
  saved: SavedKey | undefined
  models: string[]
}) {
  const refresh = useRefresh()
  const label = PROVIDER_LABEL[provider]
  const model = useMutation({ mutationFn: (next: string) => changeModel(provider, next), onSuccess: refresh })
  const activate = useMutation({ mutationFn: () => activateKey(provider), onSuccess: refresh })
  const remove = useMutation({ mutationFn: () => removeKey(provider), onSuccess: refresh })
  const failure = [model, activate, remove].find((mutation) => mutation.isError)?.error
  const busy = model.isPending || activate.isPending || remove.isPending

  return (
    <>
      <TableRow>
        <TableCell>
          <div className="flex items-center gap-3">
            <ProviderLogo provider={provider} />
            <div className="flex flex-col">
              <span className="font-medium">{label}</span>
              <span className="text-caption text-muted-foreground">
                {saved ? `Key ends in ${saved.key_last4}` : 'No key saved'}
              </span>
            </div>
          </div>
        </TableCell>
        <TableCell>
          <label className="inline-flex min-h-11 items-center gap-2">
            <input
              type="radio"
              name="active-key"
              checked={saved?.is_active ?? false}
              disabled={!saved || busy}
              onChange={() => {
                activate.mutate()
              }}
              aria-label={`Use the ${label} key`}
              className="size-4 accent-primary"
            />
            <span aria-hidden="true" className="hidden sm:inline">
              {saved?.is_active ? 'In use' : 'Use this'}
            </span>
          </label>
        </TableCell>
        <TableCell>
          {saved ? (
            <ModelSelect
              provider={provider}
              value={saved.model}
              models={models}
              label={`${label} model`}
              disabled={busy}
              onChange={(next) => {
                model.mutate(next)
              }}
            />
          ) : (
            <span className="text-muted-foreground">Needs a key</span>
          )}
        </TableCell>
        <TableCell className="text-right">
          {saved && (
            <Button
              variant="ghost"
              size="icon-sm"
              icon={Delete02Icon}
              aria-label={`Remove the ${label} key`}
              loading={remove.isPending}
              disabled={busy}
              onClick={() => {
                remove.mutate()
              }}
            />
          )}
        </TableCell>
      </TableRow>
      {failure && (
        <TableRow>
          <TableCell colSpan={4}>
            <p role="alert" className="text-small text-danger-foreground">
              {errorText(failure).message} {errorText(failure).hint}
            </p>
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

function ProviderOption({ provider }: { provider: ProviderName }) {
  return (
    <span className="flex items-center gap-2">
      <ProviderLogo provider={provider} />
      {PROVIDER_LABEL[provider]}
    </span>
  )
}

function AddKeyForm({ saved, models }: { saved: SavedKey[]; models: Record<ProviderName, string[]> }) {
  const refresh = useRefresh()
  const [provider, setProvider] = useState<ProviderName>('openai')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const list = models[provider]
  const chosenModel = list.includes(model) ? model : (list[0] ?? '')
  const replacing = saved.some((key) => key.provider === provider)
  const save = useMutation({
    mutationFn: () => saveKey(provider, apiKey.trim(), chosenModel),
    onSuccess: async () => {
      // The key is cleared as soon as the server has it; it is never shown again.
      setApiKey('')
      await refresh()
    },
  })
  const failure = save.isError ? errorText(save.error) : null

  return (
    <form
      className="grid gap-4 sm:grid-cols-[12rem_minmax(0,1fr)_12rem] sm:items-end"
      onSubmit={(event) => {
        event.preventDefault()
        if (apiKey.trim()) save.mutate()
      }}
    >
      <div className="grid gap-1.5">
        <Label htmlFor="key-provider">Provider</Label>
        <Select
          value={provider}
          onValueChange={(next) => {
            setProvider(next as ProviderName)
            setModel('')
          }}
        >
          <SelectTrigger id="key-provider">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PROVIDER_ORDER.map((name) => (
              <SelectItem key={name} value={name}>
                <ProviderOption provider={name} />
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="key-value">
          {replacing ? `New ${PROVIDER_LABEL[provider]} API key` : `${PROVIDER_LABEL[provider]} API key`}
        </Label>
        <Input
          id="key-value"
          type="password"
          autoComplete="off"
          value={apiKey}
          onChange={(event) => {
            setApiKey(event.target.value)
          }}
        />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="key-model">Model</Label>
        <Select value={chosenModel} onValueChange={setModel}>
          <SelectTrigger id="key-model">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {list.map((name) => (
              <SelectItem key={name} value={name}>
                {name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="sm:col-span-3">
        <Button type="submit" icon={Key01Icon} loading={save.isPending} disabled={!apiKey.trim()}>
          {replacing ? 'Replace key' : 'Save key'}
        </Button>
      </div>
      {failure && (
        <p role="alert" className="text-small text-danger-foreground sm:col-span-3">
          {failure.message} {failure.hint}
        </p>
      )}
    </form>
  )
}

function OwnKeys() {
  const keys = useQuery(keysQuery)
  const models = useQuery(modelsQuery)
  return (
    <QueryBoundary
      query={keys}
      errorTitle="Couldn't load your keys."
      loading={<Skeleton className="h-64 w-full" />}
    >
      {(saved) => (
        <QueryBoundary
          query={models}
          errorTitle="Couldn't load the model list."
          loading={<Skeleton className="h-64 w-full" />}
        >
          {(available) => {
            const list: Record<ProviderName, string[]> = {
              gemini: available.gemini,
              openai: available.openai,
            }
            const hasActive = saved.some((key) => key.is_active)
            return (
              <div className="flex flex-col gap-6">
                {!hasActive && (
                  <p
                    role="status"
                    className="rounded-md bg-warning-subtle p-3 text-body text-warning-foreground"
                  >
                    Questions are paused until you save a key and mark it as in use. Or switch back to
                    QueryLab AI.
                  </p>
                )}
                <Table>
                  <caption className="sr-only">Your OpenAI and Gemini keys. One can be in use.</caption>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Provider</TableHead>
                      <TableHead>In use</TableHead>
                      <TableHead>Model</TableHead>
                      <TableHead>
                        <span className="sr-only">Remove</span>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {PROVIDER_ORDER.map((provider) => (
                      <KeyRow
                        key={provider}
                        provider={provider}
                        saved={saved.find((key) => key.provider === provider)}
                        models={list[provider]}
                      />
                    ))}
                  </TableBody>
                </Table>
                <section aria-labelledby="add-key" className="flex flex-col gap-4">
                  <h2 id="add-key" className="text-h3 font-semibold">
                    Add or replace a key
                  </h2>
                  <AddKeyForm saved={saved} models={list} />
                </section>
              </div>
            )
          }}
        </QueryBoundary>
      )}
    </QueryBoundary>
  )
}

/** Choose QueryLab's AI or your own. A saved key is checked with the provider, stored encrypted and never sent back. */
export function KeysPage() {
  const settings = useQuery(settingsQuery)
  return (
    <div className="flex max-w-[var(--content-max)] flex-col gap-8">
      <QueryBoundary
        query={settings}
        errorTitle="Couldn't load your AI setting."
        loading={<Skeleton className="h-28 w-full" />}
      >
        {({ source }) => (
          <>
            <SourceChoice source={source} />
            {source === 'own' && <OwnKeys />}
          </>
        )}
      </QueryBoundary>
    </div>
  )
}
