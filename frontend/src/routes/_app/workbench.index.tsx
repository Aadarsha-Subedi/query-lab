import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/workbench/')({
  beforeLoad: () => {
    throw redirect({ to: '/workbench/runs' })
  },
})
