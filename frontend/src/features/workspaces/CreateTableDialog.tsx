import { zodResolver } from '@hookform/resolvers/zod'
import { Add01Icon, Cancel01Icon } from '@hugeicons/core-free-icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useFieldArray, useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { applyApiErrors } from '@/lib/api/form-errors'

import { COLUMN_TYPES, createTable, invalidateWorkspace } from './api'

const schema = z.object({
  name: z.string().trim().min(1, 'Name the table.'),
  description: z.string(),
  columns: z
    .array(
      z.object({
        name: z.string().trim().min(1, 'Name the column.'),
        type: z.enum(COLUMN_TYPES),
        nullable: z.boolean(),
        description: z.string(),
      }),
    )
    .min(1, 'A table needs at least one column.'),
})
type Values = z.infer<typeof schema>

const NEW_COLUMN = { name: '', type: 'text', nullable: true, description: '' } as const

export function CreateTableDialog({
  workspaceId,
  onCreated,
}: {
  workspaceId: number
  onCreated: (name: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', description: '', columns: [{ ...NEW_COLUMN }] },
  })
  const columns = useFieldArray({ control: form.control, name: 'columns' })
  const mutation = useMutation({
    mutationFn: (values: Values) => createTable(workspaceId, values),
    onSuccess: async (table) => {
      await invalidateWorkspace(queryClient, workspaceId)
      setOpen(false)
      form.reset()
      onCreated(table.name)
    },
    onError: (error) => {
      setProblem(applyApiErrors(form, error, ['name', 'description']))
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
        <Button icon={Add01Icon} size="sm">
          New table
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>New table</DialogTitle>
          <DialogDescription>
            Every table also gets a hidden row id, so you do not need a key to start. Descriptions help the
            agent understand your data.
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
                  <FormLabel>Table name</FormLabel>
                  <FormControl>
                    <Input autoComplete="off" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Input autoComplete="off" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <fieldset className="grid gap-3">
              <legend className="text-body font-medium">Columns</legend>
              {columns.fields.map((item, index) => (
                <div
                  key={item.id}
                  className="grid items-start gap-2 rounded-md border p-3 sm:grid-cols-[1fr_9rem_auto_auto]"
                >
                  <FormField
                    control={form.control}
                    name={`columns.${index}.name`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="sr-only">Column {index + 1} name</FormLabel>
                        <FormControl>
                          <Input placeholder="Column name" autoComplete="off" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`columns.${index}.type`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="sr-only">Column {index + 1} type</FormLabel>
                        <Select value={field.value} onValueChange={field.onChange}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {COLUMN_TYPES.map((type) => (
                              <SelectItem key={type} value={type}>
                                {type}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`columns.${index}.nullable`}
                    render={({ field }) => (
                      <FormItem className="flex h-9 flex-row items-center gap-2">
                        <FormControl>
                          <Checkbox
                            checked={!field.value}
                            onCheckedChange={(checked) => {
                              field.onChange(checked !== true)
                            }}
                          />
                        </FormControl>
                        <FormLabel className="text-small">Required</FormLabel>
                      </FormItem>
                    )}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    icon={Cancel01Icon}
                    aria-label={`Remove column ${index + 1}`}
                    disabled={columns.fields.length === 1}
                    onClick={() => {
                      columns.remove(index)
                    }}
                  />
                  <FormField
                    control={form.control}
                    name={`columns.${index}.description`}
                    render={({ field }) => (
                      <FormItem className="sm:col-span-4">
                        <FormLabel className="sr-only">Column {index + 1} description</FormLabel>
                        <FormControl>
                          <Input
                            placeholder="What this column holds (optional)"
                            autoComplete="off"
                            {...field}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                </div>
              ))}
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon={Add01Icon}
                className="justify-self-start"
                onClick={() => {
                  columns.append({ ...NEW_COLUMN })
                }}
              >
                Add column
              </Button>
              {form.formState.errors.columns?.message && (
                <p role="alert" className="text-small text-danger-foreground">
                  {form.formState.errors.columns.message}
                </p>
              )}
            </fieldset>
            {problem && (
              <p role="alert" className="text-small text-danger-foreground">
                {problem}
              </p>
            )}
            <DialogFooter>
              <Button type="submit" icon={Add01Icon} loading={mutation.isPending}>
                Create table
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
