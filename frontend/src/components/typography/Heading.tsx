import { useEffect, type ComponentProps } from 'react'

import { appName } from '@/lib/app-name'
import { cn } from '@/lib/utils'

const LEVELS = {
  display: { tag: 'h1', className: 'text-display' },
  1: { tag: 'h1', className: 'text-h1' },
  2: { tag: 'h2', className: 'text-h2' },
  3: { tag: 'h3', className: 'text-h3' },
} as const

type HeadingProps = ComponentProps<'h1'> & { level: keyof typeof LEVELS }

/** The page's h1 names the tab too (WCAG 2.4.2): "History · Querylab". */
export function Heading({ level, className, ...props }: HeadingProps) {
  const { tag: Tag, className: size } = LEVELS[level]
  const title = Tag === 'h1' && typeof props.children === 'string' ? props.children : undefined
  useEffect(() => {
    if (title === undefined) return
    document.title = `${title} · ${appName()}`
  }, [title])
  return (
    <Tag
      className={cn(size, 'font-semibold tracking-[var(--tracking-heading)] text-foreground', className)}
      {...props}
    />
  )
}
