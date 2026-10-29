import { HugeiconsIcon, type IconSvgElement } from '@hugeicons/react'

import { cn } from '@/lib/utils'

const SIZES = { sm: 16, md: 20, lg: 24 } as const
const STROKE_WIDTH = 1.5

type IconProps = {
  icon: IconSvgElement
  size?: keyof typeof SIZES
  className?: string
  /** Give a label only when the icon is the only content; otherwise it is hidden from screen readers. */
  label?: string
}

/** The only way feature code renders a Hugeicons icon: fixed sizes and stroke. */
export function Icon({ icon, size = 'md', className, label }: IconProps) {
  return (
    <HugeiconsIcon
      icon={icon}
      size={SIZES[size]}
      strokeWidth={STROKE_WIDTH}
      className={cn('shrink-0', className)}
      aria-hidden={label ? undefined : true}
      aria-label={label}
      role={label ? 'img' : undefined}
    />
  )
}
