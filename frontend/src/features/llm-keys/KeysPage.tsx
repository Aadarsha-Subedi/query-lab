import { Delete02Icon, Key01Icon } from '@hugeicons/core-free-icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { errorText } from '@/lib/api/error-text'

import { keysQuery, removeKey, saveKey, type SavedKey } from './api'
import { PROVIDER_LABEL, PROVIDERS, type ProviderName } from './providers'

function ProviderCard({ provider, saved }: { provider: ProviderName; saved: SavedKey | undefined }) {
  const queryClient = useQueryClient()
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['llm-keys'] }),
      queryClient.invalidateQueries({ queryKey: ['agent-limits'] }),
    ])
  }
  const save = useMutation({
    mutationFn: () => saveKey(provider, apiKey.trim(), model),
    onSuccess: async () => {
      // The key is cleared as soon as the server has it; it is never shown again.
      setApiKey('')
      setModel('')
      await refresh()
    },
  })
  const remove = useMutation({ mutationFn: () => removeKey(provider), onSuccess: refresh })
  const failure = save.isError ? save.error : remove.isError ? remove.error : null
  const label = PROVIDER_LABEL[provider]
  const keyId = `key-${provider}`
  const modelId = `model-${provider}`

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {label}
          {saved ? <Badge variant="success">Key saved</Badge> : <Badge>No key</Badge>}
        </CardTitle>
        <CardDescription>
          {saved ? `Ends in ${saved.key_last4}. Model: ${saved.model}.` : 'No key saved for this provider.'}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-3"
          onSubmit={(event) => {
            event.preventDefault()
            if (apiKey.trim()) save.mutate()
          }}
        >
          <div className="grid gap-1.5">
            <Label htmlFor={keyId}>{saved ? `Replace the ${label} key` : `${label} API key`}</Label>
            <Input
              id={keyId}
              type="password"
              autoComplete="off"
              value={apiKey}
              onChange={(event) => {
                setApiKey(event.target.value)
              }}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor={modelId}>Model (optional)</Label>
            <Input
              id={modelId}
              autoComplete="off"
              placeholder="Leave empty for the default"
              value={model}
              onChange={(event) => {
                setModel(event.target.value)
              }}
            />
          </div>
          {failure && (
            <p role="alert" className="text-small text-danger-foreground">
              {errorText(failure).message} {errorText(failure).hint}
            </p>
          )}
          <div>
            <Button type="submit" icon={Key01Icon} loading={save.isPending} disabled={!apiKey.trim()}>
              {saved ? 'Replace key' : 'Save key'}
            </Button>
          </div>
        </form>
      </CardContent>
      {saved && (
        <CardFooter>
          <Button
            variant="ghost"
            size="sm"
            icon={Delete02Icon}
            loading={remove.isPending}
            onClick={() => {
              remove.mutate()
            }}
          >
            Remove {label} key
          </Button>
        </CardFooter>
      )}
    </Card>
  )
}

/** Your own provider keys. A saved key is checked with the provider, stored encrypted and never sent back. */
export function KeysPage() {
  const query = useQuery(keysQuery)
  return (
    <div className="flex flex-col gap-4">
      <p className="max-w-[var(--reading-max)] text-body text-muted-foreground">
        Without a key of your own, questions use QueryLab&apos;s shared key, which has a daily limit for
        everyone. Add your own and your questions no longer count against it. The most recently saved key is
        the one used.
      </p>
      <QueryBoundary
        query={query}
        errorTitle="Couldn't load your keys."
        loading={
          <div className="grid gap-4 md:grid-cols-2">
            {PROVIDERS.map((provider) => (
              <Skeleton key={provider} className="h-64 w-full" />
            ))}
          </div>
        }
      >
        {(saved) => (
          <div className="grid gap-4 md:grid-cols-2">
            {PROVIDERS.map((provider) => (
              <ProviderCard
                key={provider}
                provider={provider}
                saved={saved.find((key) => key.provider === provider)}
              />
            ))}
          </div>
        )}
      </QueryBoundary>
    </div>
  )
}
