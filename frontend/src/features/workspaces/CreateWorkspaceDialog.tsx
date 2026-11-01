import { zodResolver } from '@hookform/resolvers/zod'
import { Add01Icon } from '@hugeicons/core-free-icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

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
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { applyApiErrors } from '@/lib/api/form-errors'

import { createWorkspace, type WorkspaceInfo } from './api'

const schema = z.object({ name: z.string().trim().min(1, 'Give the workspace a name.') })

export function CreateWorkspaceDialog({
  disabled,
  onCreated,
}: {
  disabled?: boolean
  onCreated?: (workspace: WorkspaceInfo) => void
}) {
  const [open, setOpen] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { name: '' } })
  const mutation = useMutation({
    mutationFn: (values: z.infer<typeof schema>) => createWorkspace(values.name),
    onSuccess: async (workspace) => {
      await queryClient.invalidateQueries({ queryKey: ['workspaces'] })
      setOpen(false)
      form.reset()
      onCreated?.(workspace)
    },
    onError: (error) => {
      setProblem(applyApiErrors(form, error, ['name']))
    },
  })

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) {
          setProblem(null)
          form.reset()
        }
      }}
    >
      <DialogTrigger asChild>
        <Button icon={Add01Icon} disabled={disabled}>
          New workspace
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New workspace</DialogTitle>
          <DialogDescription>
            A private database schema of your own. Create tables, fill them, then ask questions about them.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            noValidate
            className="grid gap-4"
            onSubmit={(event) => {
              setProblem(null)
              void form.handleSubmit((values) => {
                mutation.mutate(values)
              })(event)
            }}
          >
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input autoComplete="off" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            {problem && (
              <p role="alert" className="text-small text-danger-foreground">
                {problem}
              </p>
            )}
            <DialogFooter>
              <Button type="submit" icon={Add01Icon} loading={mutation.isPending}>
                Create
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
