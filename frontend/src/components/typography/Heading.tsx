import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

const LEVELS = {
  display: { tag: 'h1', className: 'text-display' },
  1: { tag: 'h1', className: 'text-h1' },
  2: { tag: 'h2', className: 'text-h2' },
  3: { tag: 'h3', className: 'text-h3' },
} as const

type HeadingProps = ComponentProps<'h1'> & { level: keyof typeof LEVELS }

export function Heading({ level, className, ...props }: HeadingProps) {
  const { tag: Tag, className: size } = LEVELS[level]
  return (
    <Tag
      className={cn(size, 'font-semibold tracking-[var(--tracking-heading)] text-foreground', className)}
      {...props}
    />
  )
}
