import {
  AlertCircleIcon,
  ArrowRight01Icon,
  CheckmarkCircle02Icon,
  Database01Icon,
  DatabaseIcon,
  Delete02Icon,
  FilterIcon,
  InformationCircleIcon,
  Key01Icon,
  Logout01Icon,
  PlayIcon,
  Search01Icon,
  Settings02Icon,
  SparklesIcon,
  Table01Icon,
  UserIcon,
} from '@hugeicons/core-free-icons'
import { useState, type ReactNode } from 'react'

import { Heading } from '@/components/typography/Heading'
import { Text } from '@/components/typography/Text'
import { Button } from '@/components/ui/button'
import { Icon } from '@/components/ui/icon'
import { contrastOf } from '@/features/design/contrast'
import { cn } from '@/lib/utils'

export function Section({
  id,
  title,
  intro,
  children,
}: {
  id: string
  title: string
  intro?: string
  children: ReactNode
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="flex scroll-mt-28 flex-col gap-4">
      <div className="flex flex-col gap-1 border-b pb-2">
        <Heading level={2} id={`${id}-title`}>
          {title}
        </Heading>
        {intro && (
          <Text muted className="max-w-[var(--reading-max)]">
            {intro}
          </Text>
        )}
      </div>
      {children}
    </section>
  )
}

function tokenValue(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function ContrastBadge({ ratio, minimum }: { ratio: number | null; minimum: number }) {
  if (ratio === null) return null
  const passes = ratio >= minimum
  return (
    <span
      className={cn(
        'rounded-sm px-1.5 py-0.5 font-mono text-caption tabular-nums',
        passes ? 'bg-success-subtle text-success-foreground' : 'bg-danger-subtle text-danger-foreground',
      )}
      title={`WCAG AA needs ${minimum}:1`}
    >
      {ratio.toFixed(2)}:1 {passes ? 'AA' : 'fail'}
    </span>
  )
}

type Swatch = { token: string; use: string; text?: { on: string; minimum: number }[] }

const SWATCH_GROUPS: { title: string; swatches: Swatch[] }[] = [
  {
    title: 'Surfaces and text',
    swatches: [
      { token: '--background', use: 'Page' },
      { token: '--surface', use: 'Cards, panels, table body' },
      { token: '--surface-muted', use: 'Table headers, code, sidebars' },
      { token: '--border', use: 'Dividers, card edges' },
      { token: '--input', use: 'Input borders' },
      {
        token: '--foreground',
        use: 'Body text',
        text: [
          { on: '--background', minimum: 4.5 },
          { on: '--surface', minimum: 4.5 },
        ],
      },
      {
        token: '--muted-foreground',
        use: 'Secondary text, captions',
        text: [
          { on: '--background', minimum: 4.5 },
          { on: '--surface-muted', minimum: 4.5 },
        ],
      },
    ],
  },
  {
    title: 'Accent',
    swatches: [
      {
        token: '--primary',
        use: 'Main action, links, focus ring',
        text: [
          { on: '--surface', minimum: 4.5 },
          { on: '--primary-subtle', minimum: 4.5 },
        ],
      },
      { token: '--primary-foreground', use: 'Text on primary', text: [{ on: '--primary', minimum: 4.5 }] },
      { token: '--primary-subtle', use: 'Selected rows, active nav' },
    ],
  },
  {
    title: 'Status',
    swatches: [
      { token: '--success', use: 'Passed, healthy' },
      {
        token: '--success-foreground',
        use: 'Success text',
        text: [{ on: '--success-subtle', minimum: 4.5 }],
      },
      { token: '--warning', use: 'Low confidence, needs approval' },
      {
        token: '--warning-foreground',
        use: 'Warning text',
        text: [{ on: '--warning-subtle', minimum: 4.5 }],
      },
      { token: '--danger', use: 'Errors, destructive' },
      { token: '--danger-foreground', use: 'Danger text', text: [{ on: '--danger-subtle', minimum: 4.5 }] },
      { token: '--info', use: 'Neutral notices' },
      { token: '--info-foreground', use: 'Info text', text: [{ on: '--info-subtle', minimum: 4.5 }] },
    ],
  },
]

function SwatchCard({ swatch }: { swatch: Swatch }) {
  const value = tokenValue(swatch.token)
  return (
    <div className="flex flex-col overflow-hidden rounded-lg border bg-surface">
      <div className="h-16 border-b" style={{ background: `var(${swatch.token})` }} />
      <div className="flex flex-col gap-1 p-3">
        <code className="font-mono text-code font-medium">{swatch.token}</code>
        <Text variant="small" muted>
          {swatch.use}
        </Text>
        <code className="truncate font-mono text-caption text-muted-foreground" title={value}>
          {value}
        </code>
        {swatch.text?.map((pair) => (
          <div key={pair.on} className="flex items-center justify-between gap-2">
            <span
              className="rounded-sm px-1.5 py-0.5 text-small"
              style={{ color: `var(${swatch.token})`, background: `var(${pair.on})` }}
            >
              Aa on {pair.on.slice(2)}
            </span>
            <ContrastBadge ratio={contrastOf(value, tokenValue(pair.on))} minimum={pair.minimum} />
          </div>
        ))}
      </div>
    </div>
  )
}

const CHART_SAMPLE = [72, 64, 58, 49, 41, 33, 27, 18]

function ColourSection() {
  return (
    <Section
      id="colour"
      title="Colour"
      intro="Semantic tokens only. Contrast badges are computed live from the current theme and choices."
    >
      {SWATCH_GROUPS.map((group) => (
        <div key={group.title} className="flex flex-col gap-3">
          <Heading level={3}>{group.title}</Heading>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(14rem,1fr))] gap-3">
            {group.swatches.map((swatch) => (
              <SwatchCard key={swatch.token} swatch={swatch} />
            ))}
          </div>
        </div>
      ))}
      <div className="flex flex-col gap-3">
        <Heading level={3}>Charts</Heading>
        <Text muted>Eight categorical colours, in order. Values are always labelled too.</Text>
        <div className="flex flex-col gap-1.5 rounded-lg border bg-surface p-4">
          {CHART_SAMPLE.map((value, index) => (
            <div key={index} className="flex items-center gap-3">
              <code className="w-16 font-mono text-caption text-muted-foreground">chart-{index + 1}</code>
              <div
                className="h-5 rounded-sm"
                style={{ width: `${value}%`, background: `var(--chart-${index + 1})` }}
              />
              <span className="text-small tabular-nums">{value}%</span>
            </div>
          ))}
        </div>
      </div>
    </Section>
  )
}

const TYPE_SCALE = [
  { token: 'display', className: 'text-display font-semibold', sample: 'Ask your database' },
  { token: 'h1', className: 'text-h1 font-semibold', sample: 'Eval results' },
  { token: 'h2', className: 'text-h2 font-semibold', sample: 'Run history' },
  { token: 'h3', className: 'text-h3 font-semibold', sample: 'Schema' },
  {
    token: 'body-lg',
    className: 'text-body-lg',
    sample: 'Querylab shows the SQL it ran and how it got there.',
  },
  { token: 'body', className: 'text-body', sample: 'Which product categories grew fastest last quarter?' },
  { token: 'small', className: 'text-small tabular-nums', sample: '1,204 rows in 0.8 s · 3 joins' },
  { token: 'caption', className: 'text-caption font-medium', sample: 'UPDATED 3 MINUTES AGO' },
  { token: 'code', className: 'font-mono text-code', sample: 'SELECT count(*) FROM demo.orders;' },
]

function TypographySection() {
  return (
    <Section id="type" title="Typography" intro="Sans for the interface, mono for SQL and identifiers.">
      <div className="flex flex-col divide-y rounded-lg border bg-surface">
        {TYPE_SCALE.map((row) => (
          <div key={row.token} className="grid grid-cols-[8rem_1fr] items-baseline gap-4 px-4 py-3">
            <div className="flex flex-col">
              <code className="font-mono text-code">{row.token}</code>
              <span className="font-mono text-caption text-muted-foreground">
                {tokenValue(`--ds-text-${row.token}`)}
              </span>
            </div>
            <span className={cn(row.className, row.token === 'h1' && 'tracking-[var(--tracking-heading)]')}>
              {row.sample}
            </span>
          </div>
        ))}
      </div>
      <Text muted>
        Tabular figures: <span className="tabular-nums">1,111.11 · 9,999.99</span> line up in tables. Distinct
        glyphs in mono: <code className="font-mono text-code">0O 1lI rn m</code>.
      </Text>
    </Section>
  )
}

const SPACING = [1, 1.5, 2, 3, 4, 5, 6, 8, 10, 12, 16]
const RADII = ['sm', 'md', 'lg', 'full'] as const
const SHADOWS = ['sm', 'md', 'lg'] as const

function SpaceSection() {
  return (
    <Section
      id="space"
      title="Spacing, radius and elevation"
      intro="4 px grid. Flat by default; shadows only float."
    >
      <div className="flex flex-col gap-2 rounded-lg border bg-surface p-4">
        {SPACING.map((step) => (
          <div key={step} className="flex items-center gap-3">
            <code className="w-10 font-mono text-caption text-muted-foreground">{step}</code>
            <div className="h-3 rounded-sm bg-primary" style={{ width: `calc(var(--spacing) * ${step})` }} />
            <span className="text-small text-muted-foreground tabular-nums">{step * 4} px</span>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(10rem,1fr))] gap-4">
        {RADII.map((radius) => (
          <div key={radius} className="flex flex-col items-center gap-2">
            <div
              className="size-20 border-2 border-primary bg-primary-subtle"
              style={{ borderRadius: radius === 'full' ? '9999px' : `var(--ds-radius-${radius})` }}
            />
            <code className="font-mono text-caption">radius-{radius}</code>
          </div>
        ))}
        {SHADOWS.map((shadow) => (
          <div key={shadow} className="flex flex-col items-center gap-2">
            <div
              className="size-20 rounded-lg border bg-surface"
              style={{ boxShadow: `var(--ds-shadow-${shadow})` }}
            />
            <code className="font-mono text-caption">shadow-{shadow}</code>
          </div>
        ))}
      </div>
    </Section>
  )
}

const MOTION = [
  { token: 'fast', use: 'Hover, press, toggles', className: 'duration-fast' },
  { token: 'base', use: 'Menus, tabs, toasts', className: 'duration-base' },
  { token: 'slow', use: 'Dialogs, panels', className: 'duration-slow' },
] as const

function MotionSection() {
  const [moved, setMoved] = useState(false)
  return (
    <Section
      id="motion"
      title="Motion"
      intro="Explains a change, never decorates. Reduced motion becomes a fade."
    >
      <div className="flex flex-col gap-3 rounded-lg border bg-surface p-4">
        {MOTION.map((item) => (
          <div key={item.token} className="flex items-center gap-4">
            <div className="w-40">
              <code className="font-mono text-code">duration-{item.token}</code>
              <Text variant="caption" muted>
                {tokenValue(`--duration-${item.token}`)} · {item.use}
              </Text>
            </div>
            <div className="relative h-8 flex-1 rounded-md bg-surface-muted">
              <div
                className={cn(
                  'absolute top-1 left-1 size-6 rounded-sm bg-primary transition-[left] ease-standard',
                  item.className,
                  moved && 'left-[calc(100%-1.75rem)]',
                )}
              />
            </div>
          </div>
        ))}
        <div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setMoved((value) => !value)
            }}
          >
            <Icon icon={PlayIcon} size="sm" />
            Play
          </Button>
        </div>
      </div>
    </Section>
  )
}

const ICONS = [
  { name: 'Search', icon: Search01Icon },
  { name: 'Database', icon: DatabaseIcon },
  { name: 'Schema', icon: Database01Icon },
  { name: 'Table', icon: Table01Icon },
  { name: 'Run', icon: PlayIcon },
  { name: 'Filter', icon: FilterIcon },
  { name: 'Agent', icon: SparklesIcon },
  { name: 'Success', icon: CheckmarkCircle02Icon },
  { name: 'Error', icon: AlertCircleIcon },
  { name: 'Info', icon: InformationCircleIcon },
  { name: 'API key', icon: Key01Icon },
  { name: 'User', icon: UserIcon },
  { name: 'Settings', icon: Settings02Icon },
  { name: 'Delete', icon: Delete02Icon },
  { name: 'Sign out', icon: Logout01Icon },
  { name: 'Next', icon: ArrowRight01Icon },
]

function IconSection() {
  return (
    <Section id="icons" title="Icons" intro="Hugeicons, stroke rounded, 1.5 px. Sizes sm 16, md 20, lg 24.">
      <div className="grid grid-cols-[repeat(auto-fill,minmax(7rem,1fr))] gap-2">
        {ICONS.map((item) => (
          <div key={item.name} className="flex flex-col items-center gap-2 rounded-lg border bg-surface p-3">
            <div className="flex items-end gap-2 text-foreground">
              <Icon icon={item.icon} size="sm" />
              <Icon icon={item.icon} size="md" />
              <Icon icon={item.icon} size="lg" />
            </div>
            <Text variant="caption" muted>
              {item.name}
            </Text>
          </div>
        ))}
      </div>
    </Section>
  )
}

/** `revision` changes after every theme or choice change, so token values re-read. */
export function TokenSections({ revision }: { revision: number }) {
  return (
    <div key={revision} className="flex flex-col gap-12">
      <ColourSection />
      <TypographySection />
      <SpaceSection />
      <MotionSection />
      <IconSection />
    </div>
  )
}
