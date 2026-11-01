import { useQuery } from '@tanstack/react-query'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Heading } from '@/components/typography/Heading'
import { Meter } from '@/components/ui/meter'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { formatBytes } from '@/lib/format'

import { workspaceQuery } from './api'
import { RelationsTab } from './RelationsTab'
import { SqlConsole } from './SqlConsole'
import { TablesTab } from './TablesTab'

export type DetailSearch = { tab?: 'tables' | 'relations' | 'sql'; table?: string }

type Props = {
  id: number
  tab: 'tables' | 'relations' | 'sql'
  table?: string
  onChange: (search: DetailSearch) => void
}

/** One private workspace: its tables and rows, its relations, and a SQL console. */
export function WorkspaceDetail({ id, tab, table, onChange }: Props) {
  const query = useQuery(workspaceQuery(id))
  return (
    <QueryBoundary
      query={query}
      errorTitle="Couldn't load this workspace."
      loading={<Skeleton className="h-40 w-full" />}
    >
      {(workspace) => (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Heading level={2}>{workspace.name}</Heading>
            {workspace.bytes_allowed !== null && (
              <div className="flex max-w-sm flex-col gap-1">
                <Meter value={workspace.bytes_used} max={workspace.bytes_allowed} label="Storage used" />
                <span className="text-small text-muted-foreground">
                  {formatBytes(workspace.bytes_used)} of {formatBytes(workspace.bytes_allowed)} used
                </span>
              </div>
            )}
          </div>
          <Tabs
            value={tab}
            onValueChange={(next) => {
              onChange({ tab: next as DetailSearch['tab'] })
            }}
          >
            <TabsList>
              <TabsTrigger value="tables">Tables</TabsTrigger>
              <TabsTrigger value="relations">Relations</TabsTrigger>
              <TabsTrigger value="sql">SQL console</TabsTrigger>
            </TabsList>
            <TabsContent value="tables">
              <TablesTab
                workspaceId={id}
                selected={table}
                onSelect={(name) => {
                  onChange({ tab: 'tables', table: name })
                }}
              />
            </TabsContent>
            <TabsContent value="relations">
              <RelationsTab workspaceId={id} />
            </TabsContent>
            <TabsContent value="sql">
              <SqlConsole workspaceId={id} />
            </TabsContent>
          </Tabs>
        </div>
      )}
    </QueryBoundary>
  )
}
