import logo from '@/assets/logo.svg'
import { cn } from '@/lib/utils'

/** The Querylab mark (the same file as the favicon). Decorative: the name is written next to it. */
export function Logo({ className }: { className?: string }) {
  // The mark is a black tile: on the dark theme it flips to a white tile so it stays visible.
  return (
    <img src={logo} alt="" width={28} height={28} className={cn('size-7 shrink-0 dark:invert', className)} />
  )
}
