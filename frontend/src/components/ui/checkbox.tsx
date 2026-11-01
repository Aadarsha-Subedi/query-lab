import { Tick02Icon } from '@hugeicons/core-free-icons'
import { Checkbox as CheckboxPrimitive } from 'radix-ui'
import * as React from 'react'

import { Icon } from '@/components/ui/icon'
import { cn } from '@/lib/utils'

function Checkbox({ className, ...props }: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        'peer relative size-4 shrink-0 rounded-sm border border-input bg-transparent shadow-sm transition-[color,box-shadow] outline-none after:absolute after:-inset-3.5 after:content-[""] focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground pointer-coarse:size-5',
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator className="flex items-center justify-center text-current">
        <Icon icon={Tick02Icon} size="sm" />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
}

export { Checkbox }
