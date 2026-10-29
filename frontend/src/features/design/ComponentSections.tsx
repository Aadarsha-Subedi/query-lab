import { zodResolver } from '@hookform/resolvers/zod'
import {
  Delete02Icon,
  Logout01Icon,
  MoreHorizontalIcon,
  PlayIcon,
  Settings02Icon,
  UserIcon,
} from '@hugeicons/core-free-icons'
import type { ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { CodeBlock, Code } from '@/components/typography/Code'
import { Heading } from '@/components/typography/Heading'
import { Text } from '@/components/typography/Text'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Icon } from '@/components/ui/icon'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { toast } from '@/components/ui/toast-api'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { Section } from '@/features/design/TokenSections'

function Demo({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-surface p-4">
      <div className="flex items-baseline justify-between gap-4">
        <Heading level={3}>{title}</Heading>
        {note && (
          <Text variant="small" muted>
            {note}
          </Text>
        )}
      </div>
      {children}
    </div>
  )
}

const BUTTON_VARIANTS = ['primary', 'secondary', 'ghost', 'destructive', 'link'] as const

function Buttons() {
  return (
    <Demo title="Button" note="Hover, press and Tab through them for the live states.">
      <div className="grid grid-cols-[7rem_repeat(4,auto)] items-center justify-start gap-3">
        <span />
        {['Default', 'Small', 'Loading', 'Disabled'].map((label) => (
          <Text key={label} variant="caption" muted as="span">
            {label}
          </Text>
        ))}
        {BUTTON_VARIANTS.map((variant) => (
          <div key={variant} className="contents">
            <code className="font-mono text-caption text-muted-foreground">{variant}</code>
            <Button variant={variant}>Run query</Button>
            <Button variant={variant} size="sm">
              Run query
            </Button>
            <Button variant={variant} loading>
              Running
            </Button>
            <Button variant={variant} disabled>
              Run query
            </Button>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-3">
        <Button>
          <Icon icon={PlayIcon} size="sm" />
          Approve and run
        </Button>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="secondary" size="icon" aria-label="Settings">
              <Icon icon={Settings02Icon} size="md" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Settings</TooltipContent>
        </Tooltip>
        <Button variant="ghost" size="icon-sm" aria-label="More">
          <Icon icon={MoreHorizontalIcon} size="sm" />
        </Button>
      </div>
    </Demo>
  )
}

function Inputs() {
  return (
    <Demo title="Input and label">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="grid gap-1.5">
          <Label htmlFor="demo-default">Workspace name</Label>
          <Input id="demo-default" placeholder="Olist demo" />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="demo-filled">Email</Label>
          <Input id="demo-filled" defaultValue="ada@example.com" />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="demo-invalid">Password</Label>
          <Input id="demo-invalid" type="password" defaultValue="short" aria-invalid />
          <Text variant="small" className="text-danger-foreground">
            Use at least 10 characters.
          </Text>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="demo-disabled">Database</Label>
          <Input id="demo-disabled" defaultValue="querylab (read-only)" disabled />
        </div>
      </div>
    </Demo>
  )
}

const signupSchema = z.object({
  email: z.email('Enter a valid email address.'),
  password: z.string().min(10, 'Use at least 10 characters.'),
})

function SampleForm() {
  const form = useForm<z.infer<typeof signupSchema>>({
    resolver: zodResolver(signupSchema),
    defaultValues: { email: '', password: '' },
  })
  const onSubmit = form.handleSubmit((values) => {
    toast.success('Form is valid', { description: values.email })
  })
  return (
    <Demo title="Form" note="react-hook-form + Zod. Submit empty to see errors.">
      <Form {...form}>
        <form
          onSubmit={(event) => {
            void onSubmit(event)
          }}
          className="grid max-w-sm gap-4"
          noValidate
        >
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input type="email" autoComplete="email" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Password</FormLabel>
                <FormControl>
                  <Input type="password" autoComplete="new-password" {...field} />
                </FormControl>
                <FormDescription>At least 10 characters, upper- and lower-case.</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button type="submit" className="justify-self-start">
            Create account
          </Button>
        </form>
      </Form>
    </Demo>
  )
}

function Cards() {
  return (
    <Demo title="Card">
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Olist demo</CardTitle>
            <CardDescription>Shared, read-only · 9 tables · 1.6M rows</CardDescription>
          </CardHeader>
          <CardContent>
            <Text variant="small" muted>
              Brazilian e-commerce orders, customers, payments and reviews.
            </Text>
          </CardContent>
          <CardFooter>
            <Button size="sm">Open</Button>
            <Badge variant="primary">Demo</Badge>
          </CardFooter>
        </Card>
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-4 w-48" />
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-4/5" />
          </CardContent>
          <CardFooter>
            <Skeleton className="h-8 w-16" />
          </CardFooter>
        </Card>
      </div>
    </Demo>
  )
}

function Overlays() {
  return (
    <Demo title="Dialog, dropdown menu, tooltip, toast">
      <div className="flex flex-wrap items-center gap-3">
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="secondary">Open dialog</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete workspace</DialogTitle>
              <DialogDescription>
                This removes the workspace and its tables. Runs that used it stay in your history.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="secondary">Cancel</Button>
              </DialogClose>
              <DialogClose asChild>
                <Button variant="destructive">Delete workspace</Button>
              </DialogClose>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="secondary">
              <Avatar className="size-5">
                <AvatarFallback>AS</AvatarFallback>
              </Avatar>
              Account
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuLabel>ada@example.com</DropdownMenuLabel>
            <DropdownMenuItem>
              <Icon icon={UserIcon} size="sm" />
              Profile
            </DropdownMenuItem>
            <DropdownMenuItem disabled>
              <Icon icon={Settings02Icon} size="sm" />
              Settings (disabled)
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive">
              <Icon icon={Delete02Icon} size="sm" />
              Delete account
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Icon icon={Logout01Icon} size="sm" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost">Hover for tooltip</Button>
          </TooltipTrigger>
          <TooltipContent>The model is 62% confident</TooltipContent>
        </Tooltip>

        <Separator orientation="vertical" className="h-6" />

        <Button
          variant="secondary"
          size="sm"
          onClick={() => toast.success('Query finished', { description: '1,204 rows in 0.8 s' })}
        >
          Success toast
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() =>
            toast.warning('Low confidence', { description: 'Review the SQL before running it.' })
          }
        >
          Warning toast
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => toast.error('Too many requests', { description: 'Try again in 30 seconds.' })}
        >
          Error toast
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => toast.info('Agent is planning', { description: 'Step 2 of 4' })}
        >
          Info toast
        </Button>
      </div>
    </Demo>
  )
}

function BadgesAndAvatars() {
  return (
    <Demo title="Badge, avatar, separator">
      <div className="flex flex-wrap items-center gap-2">
        <Badge>Draft</Badge>
        <Badge variant="primary">Demo</Badge>
        <Badge variant="success">Passed</Badge>
        <Badge variant="warning">Low confidence</Badge>
        <Badge variant="danger">Failed</Badge>
        <Badge variant="info">Running</Badge>
      </div>
      <Separator />
      <div className="flex items-center gap-3">
        <Avatar>
          <AvatarImage src="/missing-avatar.png" alt="" />
          <AvatarFallback>AS</AvatarFallback>
        </Avatar>
        <Avatar className="size-10">
          <AvatarFallback>QL</AvatarFallback>
        </Avatar>
        <Text variant="small" muted>
          The image fails to load, so the fallback initials show.
        </Text>
      </div>
    </Demo>
  )
}

const SAMPLE_SQL = `SELECT p.product_category_name AS category,
       count(DISTINCT o.order_id)    AS orders,
       round(sum(i.price + i.freight_value), 2) AS revenue_brl
FROM demo.orders o
JOIN demo.order_items i ON i.order_id = o.order_id
JOIN demo.products p    ON p.product_id = i.product_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= date_trunc('quarter', now()) - interval '3 months'
GROUP BY 1
ORDER BY revenue_brl DESC
LIMIT 5;`

const SAMPLE_ROWS = [
  { category: 'health_beauty', orders: 2_451, revenue: 312_844.12, change: 0.18 },
  { category: 'watches_gifts', orders: 1_604, revenue: 287_301.55, change: 0.11 },
  { category: 'bed_bath_table', orders: 2_896, revenue: 254_119.8, change: -0.04 },
  { category: 'sports_leisure', orders: 2_217, revenue: 231_090.47, change: 0.07 },
  { category: 'computers_accessories', orders: 1_713, revenue: 219_876.33, change: -0.12 },
]

const brl = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const count = new Intl.NumberFormat('en-US')
const percent = new Intl.NumberFormat('en-US', { style: 'percent', signDisplay: 'exceptZero' })

function QueryResult() {
  return (
    <Demo title="Sample: SQL and results" note="How a run will look in the analyst view.">
      <Text>
        <span className="font-medium">Question:</span> Which categories brought in the most revenue last
        quarter?
      </Text>
      <div className="flex items-center gap-2">
        <Badge variant="success">Ran on the read-only reader</Badge>
        <Badge variant="warning">Confidence 62%</Badge>
        <Text variant="small" muted as="span">
          5 rows in 0.8 s
        </Text>
      </div>
      <Tabs defaultValue="results">
        <TabsList>
          <TabsTrigger value="results">Results</TabsTrigger>
          <TabsTrigger value="sql">SQL</TabsTrigger>
          <TabsTrigger value="trace" disabled>
            Trace
          </TabsTrigger>
        </TabsList>
        <TabsContent value="results">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>category</TableHead>
                <TableHead className="text-right">orders</TableHead>
                <TableHead className="text-right">revenue_brl</TableHead>
                <TableHead className="text-right">vs previous</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {SAMPLE_ROWS.map((row, index) => (
                <TableRow key={row.category} data-state={index === 0 ? 'selected' : undefined}>
                  <TableCell>
                    <Code>{row.category}</Code>
                  </TableCell>
                  <TableCell className="text-right">{count.format(row.orders)}</TableCell>
                  <TableCell className="text-right">{brl.format(row.revenue)}</TableCell>
                  <TableCell
                    className={
                      row.change >= 0
                        ? 'text-right text-success-foreground'
                        : 'text-right text-danger-foreground'
                    }
                  >
                    {percent.format(row.change)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
            <TableCaption>First row selected. Hover a row for the hover state.</TableCaption>
          </Table>
        </TabsContent>
        <TabsContent value="sql">
          <CodeBlock code={SAMPLE_SQL} />
        </TabsContent>
      </Tabs>
    </Demo>
  )
}

export function ComponentSections() {
  return (
    <Section
      id="components"
      title="Components"
      intro="Everything lives in src/components/ui; features import from there."
    >
      <QueryResult />
      <Buttons />
      <Inputs />
      <SampleForm />
      <Cards />
      <Overlays />
      <BadgesAndAvatars />
    </Section>
  )
}
