import type { ReactNode } from 'react'
import { Link } from '@tanstack/react-router'

import { Heading } from '@/components/typography/Heading'
import { Text } from '@/components/typography/Text'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'

const QUESTIONS: { question: string; answer: ReactNode }[] = [
  {
    question: 'Is my data safe?',
    answer: (
      <>
        Treat Querylab as a demo, not a vault. A private workspace is a read-only copy only your account can
        query, and your LLM key is encrypted. But to answer a question, the model is sent your schema, common
        values from some text columns, and sometimes a few result rows. Do not upload personal, sensitive or
        production data. The{' '}
        <Link to="/privacy" className="underline underline-offset-4">
          Privacy Policy
        </Link>{' '}
        has the details.
      </>
    ),
  },
  {
    question: 'What can I import?',
    answer:
      'A plain-SQL pg_dump, as .sql or .sql.gz, of up to 50 MB. You can have up to 3 private workspaces. A workspace is read-only: to change its data, import a new dump over it.',
  },
  {
    question: 'Which models?',
    answer:
      'Gemini models on the shared key. With your own key, Gemini or OpenAI models. The Settings page lists what you can pick.',
  },
  {
    question: 'Is it free?',
    answer:
      'Yes. There is no plan and no payment. The shared key has a daily limit per user. If you use your own key, your provider bills you for what you use.',
  },
  {
    question: 'Is this a real product?',
    answer:
      'No. It is a learning and portfolio project, run by one person. It can change or disappear at any time, and data and accounts may be wiped without notice.',
  },
]

export function Faq() {
  return (
    <section
      id="faq"
      aria-labelledby="faq-title"
      className="mx-auto grid max-w-[var(--content-max)] scroll-mt-20 gap-8 px-6 py-16 lg:grid-cols-[1fr_2fr]"
    >
      <div className="flex flex-col gap-2">
        <Heading level={2} id="faq-title">
          FAQ
        </Heading>
        <Text muted>What people tend to ask before signing in.</Text>
      </div>
      <Accordion type="single" collapsible>
        {QUESTIONS.map(({ question, answer }, index) => (
          <AccordionItem key={question} value={question}>
            <AccordionTrigger>
              <span className="grid flex-1 grid-cols-[1.5rem_1fr] gap-x-2">
                <span aria-hidden className="text-muted-foreground tabular-nums">
                  {index + 1}
                </span>
                <span>{question}</span>
              </span>
            </AccordionTrigger>
            <AccordionContent className="max-w-[70ch] pl-8">{answer}</AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </section>
  )
}
