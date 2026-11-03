import { SentIcon } from '@hugeicons/core-free-icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useState, type SyntheticEvent, type KeyboardEvent } from 'react'

import { Button } from '@/components/ui/button'
import { InputGroup, InputGroupAddon, InputGroupTextarea } from '@/components/ui/input-group'

import { ApiError } from '@/lib/api'

import { createRun } from './api'
import { errorText } from '@/lib/api/error-text'

/** Errors where a key of the user's own is the way out. */
const KEY_CODES = new Set([
  'default_key_limit',
  'llm_invalid_key',
  'llm_insufficient_quota',
  'llm_rate_limited',
])

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
    // Enter sends, like a chat; Shift+Enter makes a new line.
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }
  const failure = mutation.isError ? errorText(mutation.error) : null
  const code = mutation.error instanceof ApiError ? mutation.error.code : ''

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <InputGroup>
        <InputGroupTextarea
          aria-label="Your question"
          placeholder="Ask a question about your data, for example: which product categories sold best last month?"
          className="min-h-16 p-3"
          value={question}
          onChange={(event) => {
            setQuestion(event.target.value)
          }}
          onKeyDown={onKeyDown}
          aria-invalid={failure ? true : undefined}
          aria-describedby={failure ? 'ask-error' : 'ask-hint'}
        />
        <InputGroupAddon align="block-end">
          <Button
            type="submit"
            size="icon-sm"
            icon={SentIcon}
            aria-label="Send question"
            className="ml-auto rounded-full"
            loading={mutation.isPending}
            disabled={disabled || !question.trim()}
          />
        </InputGroupAddon>
      </InputGroup>
      {failure && (
        <p id="ask-error" role="alert" className="text-small text-danger-foreground">
          {failure.message} {failure.hint}
          {KEY_CODES.has(code) && (
            <>
              {' '}
              <Link to="/settings" className="underline underline-offset-4">
                Add your own key
              </Link>
            </>
          )}
        </p>
      )}
      <p id="ask-hint" className="text-caption text-muted-foreground">
        {disabled ? 'Finish or cancel your open run first.' : 'Enter to send, Shift+Enter for a new line.'}
      </p>
    </form>
  )
}
