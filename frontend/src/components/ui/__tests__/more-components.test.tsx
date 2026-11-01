import { Delete02Icon } from '@hugeicons/core-free-icons'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'

describe('Textarea', () => {
  it('takes typing and shows the invalid state', async () => {
    render(<Textarea aria-label="Question" aria-invalid />)
    const box = screen.getByRole('textbox', { name: 'Question' })
    await userEvent.type(box, 'hello')
    expect(box).toHaveValue('hello')
    expect(box).toHaveAttribute('aria-invalid', 'true')
  })
})

describe('Checkbox and Switch', () => {
  it('toggle by click and report their state', async () => {
    render(
      <>
        <Checkbox aria-label="Only results" />
        <Switch aria-label="Assumptions" />
      </>,
    )
    const check = screen.getByRole('checkbox', { name: 'Only results' })
    const toggle = screen.getByRole('switch', { name: 'Assumptions' })
    await userEvent.click(check)
    await userEvent.click(toggle)
    expect(check).toBeChecked()
    expect(toggle).toBeChecked()
  })
})

describe('Popover and Sheet', () => {
  it('open from their triggers', async () => {
    render(
      <>
        <Popover>
          <PopoverTrigger>More</PopoverTrigger>
          <PopoverContent>Guard note</PopoverContent>
        </Popover>
        <Sheet>
          <SheetTrigger>Details</SheetTrigger>
          <SheetContent>
            <SheetTitle>Table</SheetTitle>
            <SheetDescription>Columns</SheetDescription>
          </SheetContent>
        </Sheet>
      </>,
    )
    await userEvent.click(screen.getByText('More'))
    expect(await screen.findByText('Guard note')).toBeVisible()
    await userEvent.keyboard('{Escape}')
    await userEvent.click(screen.getByText('Details'))
    expect(await screen.findByRole('dialog', { name: 'Table' })).toBeVisible()
  })
})

describe('AlertDialog', () => {
  function Subject({ onConfirm }: { onConfirm: () => void }) {
    return (
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button icon={Delete02Icon}>Delete</Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete it?</AlertDialogTitle>
            <AlertDialogDescription>This cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel />
            <AlertDialogAction icon={Delete02Icon} onClick={onConfirm}>
              Confirm
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    )
  }

  it('runs the action only after the confirm button', async () => {
    const onConfirm = vi.fn()
    render(<Subject onConfirm={onConfirm} />)
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
    expect(onConfirm).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Confirm' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })
})

describe('ScrollArea', () => {
  it('renders its children', () => {
    render(<ScrollArea>content</ScrollArea>)
    expect(screen.getByText('content')).toBeInTheDocument()
  })
})
