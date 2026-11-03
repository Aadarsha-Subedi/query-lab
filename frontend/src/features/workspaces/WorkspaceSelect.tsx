import { useQuery } from '@tanstack/react-query'

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'

import { workspacesQuery } from './api'

const DEMO = 'demo'

/** Which workspace the question is about. Its own loading and error box; an error leaves the demo usable. */
export function WorkspaceSelect({
  workspace,
  onChange,
  className = 'w-56',
}: {
  workspace?: number
  onChange: (workspace: number | undefined) => void
  className?: string
}) {
  const query = useQuery(workspacesQuery)
  if (query.isPending || (query.isError && query.isFetching))
    return <Skeleton className={`h-8 ${className}`} />
  if (query.isError) {
    return <span className="text-small text-muted-foreground">Workspaces unavailable. Using the demo.</span>
  }
  return (
    <Select
      value={workspace === undefined ? DEMO : String(workspace)}
      onValueChange={(value) => {
        onChange(value === DEMO ? undefined : Number(value))
      }}
    >
      <SelectTrigger aria-label="Workspace" className={className}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {query.data.map((item) => (
          <SelectItem key={item.id ?? DEMO} value={item.id === null ? DEMO : String(item.id)}>
            {item.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
