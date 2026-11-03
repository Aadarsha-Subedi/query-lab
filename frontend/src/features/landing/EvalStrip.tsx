import { Heading } from '@/components/typography/Heading'
import { Text } from '@/components/typography/Text'

/** From backend/DECISION.md, "Baseline results". Change them only when that section changes. */
const SCORES = [
  { value: '95.1%', name: 'Olist golden set', detail: '39 of 41 questions correct.' },
  {
    value: '86.6%',
    name: 'Spider held-out',
    detail: '362 of 418 scored questions correct; 84.2% if the 12 failed calls count as wrong.',
  },
]

export function EvalStrip() {
  return (
    <section id="evals" aria-labelledby="evals-title" className="scroll-mt-20 border-y bg-surface-muted">
      <div className="mx-auto grid max-w-[var(--content-max)] gap-8 px-6 py-16 lg:grid-cols-2">
        <div className="flex flex-col gap-2">
          <Heading level={2} id="evals-title">
            Baseline scores
          </Heading>
          <Text muted className="max-w-prose">
            A question counts as correct when its SQL returns the same rows as the reference query. Measured
            on one direct question-to-SQL call with gemini-3.5-flash-lite, prompt v1, on 2026-10-31. The agent
            has not been scored yet.
          </Text>
        </div>
        <dl className="grid gap-6 sm:grid-cols-2">
          {SCORES.map((score) => (
            <div key={score.name} className="flex flex-col gap-1">
              <dt className="text-small font-medium">{score.name}, baseline</dt>
              <dd className="text-display font-semibold tracking-[var(--tracking-heading)] tabular-nums">
                {score.value}
              </dd>
              <dd className="text-small text-muted-foreground">{score.detail}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  )
}
