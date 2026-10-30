import { HugeiconsIcon, type IconSvgElement } from '@hugeicons/react'

import { cn } from '@/lib/utils'

/*
 * Icons render only at whole-pixel sizes on the 16 / 20 / 24 grid, with a
 * size class (so no parent rule can rescale them) and an absolute stroke
 * width (so lines keep the same weight at every size instead of thinning out
 * when scaled). overflow-visible keeps stroke ends from being clipped at the
 * viewBox edge; block + shrink-0 keep them centred and unsqueezed in flex rows.
 */
const SIZES = {
  sm: { px: 16, className: 'size-4' },
  md: { px: 20, className: 'size-5' },
  lg: { px: 24, className: 'size-6' },
} as const
const STROKE_WIDTH = 1.5

export type IconSize = keyof typeof SIZES
export type { IconSvgElement }

type IconProps = {
  icon: IconSvgElement
  size?: IconSize
  className?: string
  /** Give a label only when the icon is the only content; otherwise it is hidden from screen readers. */
  label?: string
}

/** The only way feature code renders a Hugeicons icon. */
export function Icon({ icon, size = 'md', className, label }: IconProps) {
  const { px, className: sizeClass } = SIZES[size]
  return (
    <HugeiconsIcon
      icon={icon}
      size={px}
      strokeWidth={STROKE_WIDTH}
      absoluteStrokeWidth
      data-slot="icon"
      className={cn('block shrink-0 overflow-visible', sizeClass, className)}
      aria-hidden={label ? undefined : true}
      aria-label={label}
      role={label ? 'img' : undefined}
    />
  )
}
