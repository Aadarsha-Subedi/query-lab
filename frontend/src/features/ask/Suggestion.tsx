import { SparklesIcon } from '@hugeicons/core-free-icons'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/** shadcn Suggestion: a short prompt you send in one click; the label is the message. */
export function Suggestion({ text, onSelect }: { text: string; onSelect: (text: string) => void }) {
  return (
    <Button
      variant="secondary"
      size="sm"
      icon={SparklesIcon}
      className="h-auto max-w-full py-1.5 text-left whitespace-normal"
      onClick={() => {
        onSelect(text)
      }}
    >
      {text}
    </Button>
  )
}

/** The suggestions, wrapping onto new lines when they do not fit in one row. */
export function Suggestions({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div role="group" aria-label="Example questions" className={cn('flex flex-wrap gap-2', className)}>
      {children}
    </div>
  )
}
