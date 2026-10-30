/*
 * The data-state pattern (design-system.md section 13) for one component's
 * query: loading skeleton, inline error with Try again (this query only),
 * empty state, or the content. The state never leaves the component's box.
 */
import type { UseQueryResult } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { ErrorState } from '@/components/ui/data-state'
import { ApiError } from '@/lib/api'

type QueryBoundaryProps<T> = {
  query: UseQueryResult<T>
  /** Skeleton shaped like the content, at the content's size. */
  loading: ReactNode
  /** What failed, in plain words: "Couldn't load run history." */
  errorTitle: string
  /** When the data counts as empty, and what to show then. */
  isEmpty?: (data: T) => boolean
  empty?: ReactNode
  children: (data: T) => ReactNode
}

const NEXT_STEP = 'Try again, or refresh the page.'

function describe(error: Error): string {
  return `${error.message} ${NEXT_STEP}`
}

export function QueryBoundary<T>({
  query,
  loading,
  errorTitle,
  isEmpty,
  empty,
  children,
}: QueryBoundaryProps<T>) {
  // Retrying after an error goes back to the loading state.
  if (query.isPending || (query.isError && query.isFetching)) {
    return (
      <div aria-busy="true" data-state="loading">
        {loading}
      </div>
    )
  }
  if (query.isError) {
    return (
      <ErrorState
        title={errorTitle}
        description={describe(query.error)}
        requestId={query.error instanceof ApiError ? (query.error.requestId ?? undefined) : undefined}
        onRetry={() => {
          void query.refetch()
        }}
      />
    )
  }
  if (isEmpty?.(query.data) && empty) return <>{empty}</>
  return <>{children(query.data)}</>
}
