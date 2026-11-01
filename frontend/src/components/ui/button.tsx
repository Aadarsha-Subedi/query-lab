import { Loading03Icon } from '@hugeicons/core-free-icons'
import { cva, type VariantProps } from 'class-variance-authority'
import { Slot } from 'radix-ui'
import * as React from 'react'

import { Icon, type IconSize, type IconSvgElement } from '@/components/ui/icon'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  // Focus: a solid ring with a background-coloured gap, visible even around a black button.
  'inline-flex shrink-0 items-center justify-center gap-2 rounded-md text-body font-medium whitespace-nowrap transition-[color,background-color,border-color,box-shadow,transform] duration-fast outline-none select-none active:translate-y-px focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive [&_svg]:pointer-events-none',
  {
    variants: {
      variant: {
        primary: 'bg-primary text-primary-foreground hover:bg-primary/85 hover:shadow-sm',
        secondary: 'border bg-surface text-foreground shadow-sm hover:bg-surface-muted dark:border-input',
        ghost: 'text-foreground hover:bg-surface-muted',
        destructive: 'bg-danger text-primary-foreground hover:bg-danger/90',
        link: 'text-primary underline underline-offset-4 hover:decoration-2',
      },
      size: {
        sm: 'h-8 gap-1.5 px-3 text-small pointer-coarse:h-11',
        md: 'h-9 px-4 pointer-coarse:h-11',
        'icon-sm': 'size-8 pointer-coarse:size-11',
        icon: 'size-9 pointer-coarse:size-11',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
)

const ICON_SIZE: Record<NonNullable<VariantProps<typeof buttonVariants>['size']>, IconSize> = {
  sm: 'sm',
  md: 'md',
  'icon-sm': 'sm',
  icon: 'md',
}

type BaseProps = Omit<React.ComponentProps<'button'>, 'children' | 'aria-label'> &
  Pick<VariantProps<typeof buttonVariants>, 'variant'> & {
    /** Every button has an icon (design-system rule). */
    icon: IconSvgElement
    /** Which side of the label the icon sits on. */
    iconPosition?: 'start' | 'end'
    /** Swaps the icon for a spinner in the same spot (no layout shift), disables and sets aria-busy. */
    loading?: boolean
    asChild?: boolean
  }

type LabelledProps = BaseProps & {
  size?: 'sm' | 'md'
  children: React.ReactNode
  'aria-label'?: string
}

/** Icon-only buttons have no visible text, so an aria-label is required. */
type IconOnlyProps = BaseProps & {
  size: 'icon' | 'icon-sm'
  children?: never
  'aria-label': string
}

export type ButtonProps = LabelledProps | IconOnlyProps

/** shadcn/ui button with Querylab's variants, a required icon and a loading state. */
function Button({
  className,
  variant = 'primary',
  size = 'md',
  icon,
  iconPosition = 'start',
  loading = false,
  asChild = false,
  disabled,
  children,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot.Root : 'button'
  const glyph = (
    <Icon
      icon={loading ? Loading03Icon : icon}
      size={ICON_SIZE[size]}
      className={loading ? 'animate-spin' : undefined}
    />
  )

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
      {iconPosition === 'start' && glyph}
      <Slot.Slottable>{children}</Slot.Slottable>
      {iconPosition === 'end' && glyph}
    </Comp>
  )
}

export { Button }
