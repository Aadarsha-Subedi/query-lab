import { Add01Icon, Delete02Icon, Key01Icon } from '@hugeicons/core-free-icons'
import { useMutation, useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Heading } from '@/components/typography/Heading'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/data-state'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { errorText } from '@/lib/api/error-text'

import {
  activateKey,
  changeModel,
  keysQuery,
  modelsQuery,
  removeKey,
  setQuerylabModel,
  setSource,
  settingsQuery,
  type AiSource,
  type SavedKey,
} from './api'
import { AddKeyDialog } from './AddKeyDialog'
import { ProviderLogo } from './ProviderLogo'
import { PROVIDER_LABEL, PROVIDER_ORDER, type ProviderName } from './providers'
import { useRefresh } from './use-refresh'
import { UsageSection } from '@/features/limits/UsageSection'

const SOURCE_LABEL: Record<AiSource, string> = { querylab: 'QueryLab AI', own: 'Custom AI' }

/** One setting: title and description on the left, the control on the right. */
function SettingRow({
  id,
  title,
  description,
  failure,
  children,
}: {
  id: string
  title: string
  description: string
  failure: { message: string; hint: string } | null
  children: ReactNode
}) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div className="flex max-w-[var(--reading-max)] flex-col gap-1">
          <Heading level={2} id={id}>
            {title}
          </Heading>
          <p className="text-body text-muted-foreground">{description}</p>
        </div>
        <div className="w-full sm:w-56 sm:shrink-0">{children}</div>
      </div>
      {failure && (
        <p role="alert" className="text-small text-danger-foreground">
          {failure.message} {failure.hint}
        </p>
      )}
    </section>
  )
}

function SourceSetting({ source }: { source: AiSource }) {
  const refresh = useRefresh()
  const mutation = useMutation({ mutationFn: setSource, onSuccess: refresh })
  return (
    <SettingRow
      id="ai-source"
      title="AI for your questions"
      description="QueryLab AI needs no setup and uses our shared key, which has a daily limit for everyone. A custom AI uses your own OpenAI or Gemini key, with no daily limit from us."
      failure={mutation.isError ? errorText(mutation.error) : null}
    >
      <Select
        value={source}
        disabled={mutation.isPending}
        onValueChange={(next) => {
          mutation.mutate(next as AiSource)
        }}
      >
        <SelectTrigger aria-labelledby="ai-source" className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {(Object.keys(SOURCE_LABEL) as AiSource[]).map((value) => (
            <SelectItem key={value} value={value}>
              {SOURCE_LABEL[value]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </SettingRow>
  )
}

/** Which Gemini model answers on QueryLab's shared key. */
function QuerylabModelSetting({ model }: { model: string }) {
  const refresh = useRefresh()
  const models = useQuery(modelsQuery)
  const mutation = useMutation({ mutationFn: setQuerylabModel, onSuccess: refresh })
  return (
    <QueryBoundary
      query={models}
      errorTitle="Couldn't load the model list."
      loading={<Skeleton className="h-16 w-full" />}
    >
      {(available) => (
        <SettingRow
          id="querylab-model"
          title="QueryLab AI model"
          description="The Gemini model that answers on our shared key. Larger models can be slower."
          failure={mutation.isError ? errorText(mutation.error) : null}
        >
          <ModelSelect
            provider="gemini"
            value={model}
            models={available.gemini}
            label="QueryLab AI model"
            disabled={mutation.isPending}
            onChange={(next) => {
              mutation.mutate(next)
            }}
          />
        </SettingRow>
      )}
    </QueryBoundary>
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
      <SelectTrigger aria-label={label} className="w-full min-w-44" data-provider={provider}>
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

function KeyRow({ saved, models }: { saved: SavedKey; models: Record<ProviderName, string[]> }) {
  const refresh = useRefresh()
  const provider = saved.provider as ProviderName
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
              <span className="text-caption text-muted-foreground">Key ends in {saved.key_last4}</span>
            </div>
          </div>
        </TableCell>
        <TableCell>
          <label className="inline-flex min-h-11 items-center gap-2">
            <input
              type="radio"
              name="active-key"
              checked={saved.is_active}
              disabled={busy}
              onChange={() => {
                activate.mutate()
              }}
              aria-label={`Use the ${label} key`}
              className="size-4 accent-primary"
            />
            <span aria-hidden="true" className="hidden sm:inline">
              {saved.is_active ? 'In use' : 'Use this'}
            </span>
          </label>
        </TableCell>
        <TableCell>
          <ModelSelect
            provider={provider}
            value={saved.model}
            models={models[provider]}
            label={`${label} model`}
            disabled={busy}
            onChange={(next) => {
              model.mutate(next)
            }}
          />
        </TableCell>
        <TableCell>
          <div className="flex justify-end gap-1">
            <AddKeyDialog
              replacing
              providers={[provider]}
              models={models}
              trigger={
                <Button
                  variant="ghost"
                  size="icon-sm"
                  icon={Key01Icon}
                  aria-label={`Replace the ${label} key`}
                  disabled={busy}
                />
              }
            />
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
          </div>
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

function CustomKeys() {
  const keys = useQuery(keysQuery)
  const models = useQuery(modelsQuery)
  return (
    <QueryBoundary
      query={keys}
      errorTitle="Couldn't load your keys."
      loading={<Skeleton className="h-48 w-full" />}
    >
      {(saved) => (
        <QueryBoundary
          query={models}
          errorTitle="Couldn't load the model list."
          loading={<Skeleton className="h-48 w-full" />}
        >
          {(available) => {
            const list: Record<ProviderName, string[]> = {
              gemini: available.gemini,
              openai: available.openai,
            }
            const missing = PROVIDER_ORDER.filter((name) => !saved.some((key) => key.provider === name))
            const rows = PROVIDER_ORDER.flatMap((name) => saved.filter((key) => key.provider === name))
            const addTrigger = (
              <Button icon={Add01Icon} variant={rows.length === 0 ? 'primary' : 'secondary'}>
                Add new API key
              </Button>
            )
            return (
              <section aria-labelledby="your-keys" className="flex flex-col gap-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <Heading level={2} id="your-keys">
                    Your API keys
                  </Heading>
                  {rows.length > 0 && missing.length > 0 && (
                    <AddKeyDialog trigger={addTrigger} providers={missing} models={list} />
                  )}
                </div>
                {rows.length === 0 ? (
                  <div className="rounded-lg border bg-surface">
                    <EmptyState
                      icon={Key01Icon}
                      title="No API keys yet"
                      description="Add an OpenAI or Gemini key. Questions are paused until you add one."
                      action={<AddKeyDialog trigger={addTrigger} providers={missing} models={list} />}
                    />
                  </div>
                ) : (
                  <>
                    {!rows.some((key) => key.is_active) && (
                      <p
                        role="status"
                        className="rounded-md bg-warning-subtle p-3 text-body text-warning-foreground"
                      >
                        Questions are paused until a key is marked as in use. Or switch back to QueryLab AI.
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
                            <span className="sr-only">Actions</span>
                          </TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {rows.map((saved) => (
                          <KeyRow key={saved.provider} saved={saved} models={list} />
                        ))}
                      </TableBody>
                    </Table>
                  </>
                )}
              </section>
            )
          }}
        </QueryBoundary>
      )}
    </QueryBoundary>
  )
}

/** Choose QueryLab's AI or a custom one, and see the usage. A saved key is checked with the provider, stored encrypted and never sent back. */
export function KeysPage() {
  const settings = useQuery(settingsQuery)
  return (
    <div className="flex flex-col divide-y *:py-8 *:first:pt-0 *:last:pb-0">
      <QueryBoundary
        query={settings}
        errorTitle="Couldn't load your AI setting."
        loading={<Skeleton className="h-24 w-full" />}
      >
        {({ source, querylab_model }) => (
          <>
            <SourceSetting source={source} />
            {source === 'querylab' && <QuerylabModelSetting model={querylab_model} />}
            {source === 'own' && <CustomKeys />}
          </>
        )}
      </QueryBoundary>
      <UsageSection />
    </div>
  )
}
