import { useQuery } from '@tanstack/react-query'

import { QueryBoundary } from '@/components/QueryBoundary'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { healthQuery, type Health } from '@/features/health/api'

const CHECKS: { key: Exclude<keyof Health, 'status'>; label: string }[] = [
  { key: 'app_db', label: 'App database' },
  { key: 'data_db', label: 'Data database' },
  { key: 'data_reader', label: 'Read-only reader' },
  { key: 'redis', label: 'Redis' },
  { key: 'worker', label: 'Background worker' },
]

/** Live status of every backend dependency (GET /api/health). */
export function HealthPanel() {
  const query = useQuery(healthQuery)
  return (
    <Card>
      <CardHeader>
        <CardTitle>System health</CardTitle>
      </CardHeader>
      <CardContent>
        <QueryBoundary
          query={query}
          errorTitle="Couldn't load system health."
          loading={
            <ul className="flex flex-col gap-2">
              {CHECKS.map((check) => (
                <li key={check.key} className="flex h-6 items-center justify-between">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-4 w-10" />
                </li>
              ))}
            </ul>
          }
        >
          {(health) => (
            <ul className="flex flex-col gap-2">
              {CHECKS.map((check) => (
                <li key={check.key} className="flex h-6 items-center justify-between">
                  <span className="text-body">{check.label}</span>
                  <Badge variant={health[check.key] === 'ok' ? 'success' : 'danger'}>
                    {health[check.key] === 'ok' ? 'OK' : 'Failing'}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </QueryBoundary>
      </CardContent>
    </Card>
  )
}
