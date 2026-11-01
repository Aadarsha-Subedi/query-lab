import { SentIcon } from '@hugeicons/core-free-icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type SyntheticEvent, type KeyboardEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

import { createRun } from './api'
import { errorText } from './errors'

type AskBoxProps = {
  /** Fills the box on first render (the page remounts it with a new key to load an example). */
  initialQuestion?: string
  workspace?: number
  /** True while another run of this user is still open: the server would refuse a new one. */
  disabled?: boolean
  onStarted: (runId: number) => void
}

/** The question box. Ctrl/Cmd+Enter sends. The text stays after an error so it can be edited. */
export function AskBox({ initialQuestion = '', workspace, disabled, onStarted }: AskBoxProps) {
  const [question, setQuestion] = useState(initialQuestion)
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: () => createRun(question.trim(), workspace),
    onSuccess: (run) => {
      setQuestion('')
      void queryClient.invalidateQueries({ queryKey: ['agent-limits'] })
      onStarted(run.id)
    },
  })

  const submit = (event?: SyntheticEvent) => {
    event?.preventDefault()
    if (!question.trim() || mutation.isPending || disabled) return
    mutation.mutate()
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) submit()
  }
  const failure = mutation.isError ? errorText(mutation.error) : null

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <Textarea
        aria-label="Your question"
        placeholder="Ask a question about your data, for example: which product categories sold best last month?"
        value={question}
        onChange={(event) => {
          setQuestion(event.target.value)
        }}
        onKeyDown={onKeyDown}
        aria-invalid={failure ? true : undefined}
        aria-describedby={failure ? 'ask-error' : undefined}
      />
      {failure && (
        <p id="ask-error" role="alert" className="text-small text-danger-foreground">
          {failure.message} {failure.hint}
        </p>
      )}
      <div className="flex items-center justify-between gap-3">
        <span className="text-small text-muted-foreground">
          {disabled ? 'Finish or cancel your open run first.' : 'Ctrl+Enter to send'}
        </span>
        <Button
          type="submit"
          icon={SentIcon}
          loading={mutation.isPending}
          disabled={disabled || !question.trim()}
        >
          Ask
        </Button>
      </div>
    </form>
  )
}
