import { createRootRouteWithContext, Outlet } from '@tanstack/react-router'

import { ThemeController } from '@/components/ThemeController'
import { Toaster } from '@/components/ui/toast'
import { TooltipProvider } from '@/components/ui/tooltip'
import type { RouterContext } from '@/router'

export const Route = createRootRouteWithContext<RouterContext>()({
  component: Root,
})

function Root() {
  return (
    <TooltipProvider>
      <ThemeController />
      <Outlet />
      <Toaster />
    </TooltipProvider>
  )
}
