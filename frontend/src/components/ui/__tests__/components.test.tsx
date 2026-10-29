import { zodResolver } from '@hookform/resolvers/zod'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { CodeBlock } from '@/components/typography/Code'
import { Heading } from '@/components/typography/Heading'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

describe('Button', () => {
  it('is disabled and busy while loading', () => {
    render(<Button loading>Running</Button>)
    const button = screen.getByRole('button', { name: 'Running' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
  })

  it('applies the variant', () => {
    render(<Button variant="destructive">Delete workspace</Button>)
    expect(screen.getByRole('button')).toHaveClass('bg-danger')
  })
})

describe('typography and tokens', () => {
  it('keeps the type-scale size next to a colour class', () => {
    expect(cn('text-h1', 'text-foreground')).toBe('text-h1 text-foreground')
    expect(cn('text-body', 'text-small')).toBe('text-small')
  })

  it('renders heading levels as the right element', () => {
    render(<Heading level={2}>Run history</Heading>)
    expect(screen.getByRole('heading', { level: 2, name: 'Run history' })).toHaveClass('text-h2')
  })

  it('highlights SQL keywords without changing the text', () => {
    const { container } = render(<CodeBlock code="SELECT 1 FROM demo.orders" />)
    expect(container.querySelector('code')).toHaveTextContent('SELECT 1 FROM demo.orders')
    expect(screen.getByText('SELECT')).toHaveClass('text-primary')
  })
})

describe('Badge', () => {
  it.each(['neutral', 'primary', 'success', 'warning', 'danger', 'info'] as const)(
    'renders %s',
    (variant) => {
      render(<Badge variant={variant}>{variant}</Badge>)
      expect(screen.getByText(variant)).toBeInTheDocument()
    },
  )
})

const schema = z.object({ email: z.email('Enter a valid email address.') })

function SampleForm() {
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { email: '' },
  })
  return (
    <Form {...form}>
      <form
        onSubmit={(event) => {
          void form.handleSubmit(() => undefined)(event)
        }}
      >
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit">Save</Button>
      </form>
    </Form>
  )
}

describe('Form', () => {
  it('links the label and announces the Zod error', async () => {
    render(<SampleForm />)
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    const message = await screen.findByText('Enter a valid email address.')
    const input = screen.getByLabelText('Email')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input.getAttribute('aria-describedby')).toContain(message.id)
  })
})

describe('overlays and tabs', () => {
  it('opens a dialog', async () => {
    render(
      <Dialog>
        <DialogTrigger>Open</DialogTrigger>
        <DialogContent>
          <DialogTitle>Delete workspace</DialogTitle>
        </DialogContent>
      </Dialog>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Open' }))
    expect(await screen.findByRole('dialog', { name: 'Delete workspace' })).toBeInTheDocument()
  })

  it('opens a dropdown menu', async () => {
    render(
      <DropdownMenu>
        <DropdownMenuTrigger>Account</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem>Sign out</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Account' }))
    expect(await screen.findByRole('menuitem', { name: 'Sign out' })).toBeInTheDocument()
  })

  it('shows a tooltip on hover', async () => {
    render(
      <TooltipProvider delayDuration={0}>
        <Tooltip>
          <TooltipTrigger>Settings</TooltipTrigger>
          <TooltipContent>Open settings</TooltipContent>
        </Tooltip>
      </TooltipProvider>,
    )
    await userEvent.hover(screen.getByRole('button', { name: 'Settings' }))
    expect(await screen.findByRole('tooltip')).toHaveTextContent('Open settings')
  })

  it('switches tabs', async () => {
    render(
      <Tabs defaultValue="results">
        <TabsList>
          <TabsTrigger value="results">Results</TabsTrigger>
          <TabsTrigger value="sql">SQL</TabsTrigger>
        </TabsList>
        <TabsContent value="results">rows</TabsContent>
        <TabsContent value="sql">select</TabsContent>
      </Tabs>,
    )
    await userEvent.click(screen.getByRole('tab', { name: 'SQL' }))
    expect(screen.getByRole('tab', { name: 'SQL' })).toHaveAttribute('aria-selected', 'true')
  })
})
