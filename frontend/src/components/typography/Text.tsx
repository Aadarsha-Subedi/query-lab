import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

const VARIANTS = {
  'body-lg': 'text-body-lg',
  body: 'text-body',
  small: 'text-small',
  caption: 'text-caption font-medium',
} as const

type TextProps = ComponentProps<'p'> & {
  variant?: keyof typeof VARIANTS
  muted?: boolean
  as?: 'p' | 'span' | 'div'
}

export function Text({ variant = 'body', muted = false, as: Tag = 'p', className, ...props }: TextProps) {
  return (
    <Tag
      className={cn(VARIANTS[variant], muted ? 'text-muted-foreground' : 'text-foreground', className)}
      {...props}
    />
  )
}
