import { Loading03Icon } from '@hugeicons/core-free-icons'
import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'
import { Slot } from 'radix-ui'

import { Icon } from '@/components/ui/icon'

const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-md text-body font-medium whitespace-nowrap transition-[color,background-color,border-color,box-shadow,transform] duration-fast outline-none active:translate-y-px focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        primary: 'bg-primary text-primary-foreground hover:bg-primary/90 hover:shadow-sm',
        secondary: 'border bg-surface text-foreground shadow-sm hover:bg-surface-muted dark:border-input',
        ghost: 'text-foreground hover:bg-surface-muted',
        destructive: 'bg-danger text-primary-foreground hover:bg-danger/90 focus-visible:ring-danger/30',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        sm: 'h-8 gap-1.5 px-3 text-small has-[>svg]:px-2.5',
        md: 'h-9 px-4 py-2 has-[>svg]:px-3',
        'icon-sm': 'size-8',
        icon: 'size-9',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  },
)

/** shadcn/ui button with Querylab's variants and a `loading` state. */
function Button({
  className,
  variant = 'primary',
  size = 'md',
  asChild = false,
  loading = false,
  disabled,
  children,
  ...props
}: React.ComponentProps<'button'> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
    /** Shows a spinner, disables the button and sets aria-busy. */
    loading?: boolean
  }) {
  const Comp = asChild ? Slot.Root : 'button'

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      disabled={disabled ?? loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && !asChild && <Icon icon={Loading03Icon} size="sm" className="animate-spin" />}
      {children}
    </Comp>
  )
}

export { Button }
