import type { ReactNode } from 'react'

import { CodeBlock } from '@/components/typography/Code'
import { Text } from '@/components/typography/Text'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { DEMO_EXAMPLES } from '@/features/ask/examples'

const QUESTION = DEMO_EXAMPLES[1]

const SQL = `SELECT c.customer_state AS state, COUNT(*) AS late_orders
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date > o.order_estimated_delivery_date
GROUP BY c.customer_state
ORDER BY late_orders DESC
LIMIT 4`

/** Counted from the full Olist CSVs with the same filter as the SQL above. Update both together. */
const ROWS = [
  { state: 'SP', late: '2,387' },
  { state: 'RJ', late: '1,664' },
  { state: 'MG', late: '637' },
  { state: 'BA', late: '457' },
]

/** One step of the run arrives after the other, like a replayed trace (design-system.md section 7). */
function Step({ order, className, children }: { order: 0 | 1 | 2; className?: string; children: ReactNode }) {
  const delay = [
    '',
    '[animation-delay:var(--duration-base)]',
    '[animation-delay:calc(var(--duration-base)*2)]',
  ][order]
  return (
    <div
      className={`animate-in fill-mode-backwards [animation-duration:var(--duration-base)] fade-in slide-in-from-bottom-1 motion-reduce:animate-none ${delay} ${className ?? ''}`}
    >
      {children}
    </div>
  )
}

/** Styled after the Ask page, with real demo numbers. Static: no request is made and nothing here runs. */
export function ProductPreview() {
  return (
    <figure className="flex flex-col gap-4 rounded-lg border bg-surface p-4 text-left md:p-6">
      <Step order={0} className="flex justify-end">
        <p className="max-w-prose rounded-lg bg-surface-muted px-3 py-2 text-body">{QUESTION}</p>
      </Step>
      <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
        <Step order={1} className="min-w-0">
          <CodeBlock
            code={SQL}
            className="h-full [&_button]:bg-surface-muted [&_pre]:overflow-x-auto [&_pre]:break-normal [&_pre]:whitespace-pre"
          />
        </Step>
        <Step order={2} className="flex min-w-0 flex-col gap-3">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>state</TableHead>
                <TableHead className="text-right">late_orders</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {ROWS.map((row) => (
                <TableRow key={row.state}>
                  <TableCell className="font-mono">{row.state}</TableCell>
                  <TableCell className="text-right font-mono tabular-nums">{row.late}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="success">Checked</Badge>
            <Text as="span" variant="caption" muted>
              4 rows from the Olist demo data
            </Text>
          </div>
        </Step>
      </div>
    </figure>
  )
}
