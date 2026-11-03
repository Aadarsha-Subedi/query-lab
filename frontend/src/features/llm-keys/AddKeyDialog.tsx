import { Key01Icon } from '@hugeicons/core-free-icons'
import { useMutation } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { errorText } from '@/lib/api/error-text'

import { saveKey } from './api'
import { ProviderLogo } from './ProviderLogo'
import { PROVIDER_LABEL, type ProviderName } from './providers'
import { useRefresh } from './use-refresh'

type AddKeyDialogProps = {
  /** The button that opens the dialog. */
  trigger: ReactNode
  /** Providers the user can pick (all of them when adding, one when replacing). */
  providers: readonly ProviderName[]
  models: Record<ProviderName, string[]>
  /** True when the provider already has a key, so saving replaces it. */
  replacing?: boolean
}

/** Add or replace one provider's key. The key is checked with the provider, stored encrypted and never shown again. */
export function AddKeyDialog({ trigger, providers, models, replacing = false }: AddKeyDialogProps) {
  const refresh = useRefresh()
  const [open, setOpen] = useState(false)
  const [provider, setProvider] = useState<ProviderName>(providers[0] ?? 'openai')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const list = models[provider]
  const chosenModel = list.includes(model) ? model : (list[0] ?? '')
  const save = useMutation({
    mutationFn: () => saveKey(provider, apiKey.trim(), chosenModel),
    onSuccess: async () => {
      // The key is cleared as soon as the server has it.
      setApiKey('')
      setOpen(false)
      await refresh()
    },
  })
  const failure = save.isError ? errorText(save.error) : null
  const label = PROVIDER_LABEL[provider]

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) {
          setApiKey('')
          save.reset()
        }
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{replacing ? `Replace the ${label} key` : 'Add new API key'}</DialogTitle>
          <DialogDescription>
            We check the key with the provider, store it encrypted, and never show it again.
          </DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault()
            if (apiKey.trim()) save.mutate()
          }}
        >
          <div className="grid gap-1.5">
            <Label htmlFor="key-provider">Provider</Label>
            <Select
              value={provider}
              disabled={providers.length === 1}
              onValueChange={(next) => {
                setProvider(next as ProviderName)
                setModel('')
              }}
            >
              <SelectTrigger id="key-provider" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {providers.map((name) => (
                  <SelectItem key={name} value={name}>
                    <span className="flex items-center gap-2">
                      <ProviderLogo provider={name} />
                      {PROVIDER_LABEL[name]}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="key-value">{label} API key</Label>
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
              <SelectTrigger id="key-model" className="w-full">
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
          {failure && (
            <p role="alert" className="text-small text-danger-foreground">
              {failure.message} {failure.hint}
            </p>
          )}
          <DialogFooter>
            <Button type="submit" icon={Key01Icon} loading={save.isPending} disabled={!apiKey.trim()}>
              {replacing ? 'Replace key' : 'Save key'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
