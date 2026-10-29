import { Toaster as Sonner } from 'sonner'

import { useThemeStore } from '@/stores/theme'

/** One per app. Toasts follow the theme and use the surface tokens. */
export function Toaster() {
  const preference = useThemeStore((state) => state.preference)
  return (
    <Sonner
      theme={preference}
      toastOptions={{
        classNames: {
          toast: '!rounded-lg !border !bg-surface !text-foreground !shadow-md !font-sans !text-body',
          description: '!text-muted-foreground',
          success: '[&_[data-icon]]:!text-success',
          error: '[&_[data-icon]]:!text-danger',
          warning: '[&_[data-icon]]:!text-warning',
          info: '[&_[data-icon]]:!text-info',
        },
      }}
    />
  )
}
