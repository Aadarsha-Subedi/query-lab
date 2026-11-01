import { ThumbsDownIcon, ThumbsUpIcon } from '@hugeicons/core-free-icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'

import { clearVote, voteOnRun, type Vote } from './api'
import { errorText } from '@/lib/api/error-text'

/** 👍 / 👎 on a finished run. Press the active one again to take it back. The server's answer decides the state. */
export function Feedback({ runId, vote }: { runId: number; vote: Vote | null }) {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: (next: Vote) => (next === vote ? clearVote(runId) : voteOnRun(runId, next)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['run', runId] }),
  })
  const failure = mutation.isError ? errorText(mutation.error) : null
  return (
    <div className="flex items-center gap-2" role="group" aria-label="Was this answer right?">
      <span className="text-small text-muted-foreground">Was this right?</span>
      <Button
        variant={vote === 'up' ? 'primary' : 'secondary'}
        size="icon-sm"
        icon={ThumbsUpIcon}
        aria-label="Yes, this was right"
        aria-pressed={vote === 'up'}
        disabled={mutation.isPending}
        onClick={() => {
          mutation.mutate('up')
        }}
      />
      <Button
        variant={vote === 'down' ? 'primary' : 'secondary'}
        size="icon-sm"
        icon={ThumbsDownIcon}
        aria-label="No, this was wrong"
        aria-pressed={vote === 'down'}
        disabled={mutation.isPending}
        onClick={() => {
          mutation.mutate('down')
        }}
      />
      {failure && (
        <span role="alert" className="text-small text-danger-foreground">
          {failure.message}
        </span>
      )}
    </div>
  )
}
