# Querylab design system (draft for approval)

Status: **draft, being finalized on the dev-only `/design` page.** Tokens
(`src/styles/tokens.css`), the Tailwind theme, fonts, typography and the base
components are built as described here, with the four open decisions
switchable live on `/design`. Once they are chosen, the chosen values become
the only ones and this document is updated to match.

Changes from the first draft: Animate UI was dropped for plain shadcn/ui
(owner's choice). And light `muted-foreground` is a step darker than
stone-500 (a 70/30 mix of the 500 and 600 steps). The live contrast check on
`/design` showed stone-500 at 4.39:1 on `surface-muted`, below AA; the new
value is 5.0:1 there and 5.3:1 on `background`. Every other text pair passes
in both themes, for every option.

Questions for you are marked **Decide:**. Each has a recommended default, so
"approve as is" is a complete answer.

---

## 1. Brand feel

Querylab is an analyst's instrument: you ask a question, it shows its work (the
SQL, the trace, the score). The interface should feel like a good lab notebook,
not a marketing site.

- **Precise.** Aligned grids, tabular numbers, monospaced SQL, clear states.
- **Calm.** Mostly neutral surfaces; colour is reserved for meaning (accent for
  the one primary action, semantic colours for status, chart colours for data).
- **Honest.** The UI never hides uncertainty: confidence, errors and "the model
  guessed" are shown plainly, in words as well as colour.
- **Dense but breathable.** Tables and traces carry a lot of information, so the
  spacing scale is compact, with generous space only around page-level sections.

What it is not: no gradients on surfaces, no glassmorphism, no decorative
illustrations in the app, no animation that delays reading.

## 2. Colour

Neutral base: a warm-leaning grey (Tailwind's **stone**) so long reading
sessions feel less clinical than pure grey. One accent: **indigo-blue**, chosen
for "link / primary action" and because it stays distinct from the green/amber/red
status colours. Values are given in OKLCH (what Tailwind v4 uses) with the hex
approximation beside them.

### 2.1 Semantic tokens

Components only ever use these names, never a raw colour.

| Token                | Use                                        | Light                            | Dark                            |
| -------------------- | ------------------------------------------ | -------------------------------- | ------------------------------- |
| `background`         | Page                                       | `oklch(0.985 0.001 106)` #fafaf9 | `oklch(0.16 0.004 49)` #141210  |
| `foreground`         | Body text                                  | `oklch(0.216 0.006 56)` #1c1917  | `oklch(0.97 0.001 106)` #f5f5f4 |
| `surface`            | Cards, panels, table body                  | `oklch(1 0 0)` #ffffff           | `oklch(0.21 0.006 56)` #1f1c1a  |
| `surface-muted`      | Table headers, code blocks, sidebars       | `oklch(0.97 0.001 106)` #f5f5f4  | `oklch(0.25 0.006 34)` #292524  |
| `border`             | Dividers, inputs, card edges               | `oklch(0.923 0.003 49)` #e7e5e4  | `oklch(0.32 0.006 34)` #3a3532  |
| `muted-foreground`   | Secondary text, captions, placeholders     | `oklch(0.553 0.013 58)` #78716c  | `oklch(0.709 0.01 56)` #a8a29e  |
| `primary`            | The main action, links, focus ring         | `oklch(0.51 0.19 264)` #3b55d9   | `oklch(0.68 0.15 264)` #7c93f5  |
| `primary-foreground` | Text on primary                            | `oklch(0.985 0 0)` #fafafa       | `oklch(0.16 0.004 49)` #141210  |
| `primary-subtle`     | Selected rows, active nav item background  | `oklch(0.95 0.025 264)` #e9edfd  | `oklch(0.28 0.06 264)` #243064  |
| `success`            | Correct answer, healthy check, passed eval | `oklch(0.56 0.13 152)` #1f8a4c   | `oklch(0.72 0.14 152)` #4cc27a  |
| `warning`            | Low confidence, needs approval, degraded   | `oklch(0.66 0.15 70)` #c4800f    | `oklch(0.79 0.14 75)` #e8ad3c   |
| `danger`             | Errors, failed eval, destructive actions   | `oklch(0.55 0.2 27)` #d12f2f     | `oklch(0.7 0.17 25)` #f26d63    |
| `info`               | Neutral notices, "the model is thinking"   | `oklch(0.58 0.11 230)` #2b86c0   | `oklch(0.74 0.11 230)` #5cb5e8  |

Each status colour also gets a `-subtle` background (about 10% strength) and a
`-foreground` text colour for badges and alerts, defined in 0.10.7.

Contrast targets: body text and `muted-foreground` at least 4.5:1 on
`background` and `surface`; `primary` text on `surface` at least 4.5:1; focus
rings at least 3:1 against what they surround. The values above are picked to
meet these; 0.10.7 checks each pair and adjusts if one falls short.

### 2.2 Data colours (charts, step 4 and the eval dashboard)

Eight categorical colours that stay distinguishable for the common forms of
colour blindness and work on both themes: blue, orange, teal, magenta, olive,
purple, cyan, brown (exact values in 0.10.7, validated with a simulator). A
sequential scale (single-hue blue) for heatmaps and a diverging scale
(red to blue through neutral) for "worse / better than baseline". Charts never
rely on colour alone: values are labelled or shown on hover.

**Decide:** accent colour. Recommended: indigo-blue as above. Alternatives: teal
(more "data tool", but closer to the success green) or violet (more distinctive,
less conventional for links).

## 3. Typography

Two families, both self-hosted through `@fontsource` packages (no request to
Google at runtime, works offline, no layout shift with `font-display: swap` and
matched fallbacks):

- **Inter (variable)** for the interface: very legible at small sizes, has
  tabular figures (`font-variant-numeric: tabular-nums`) for tables and scores.
- **JetBrains Mono** for SQL, column names, IDs and trace payloads: clear
  distinction between `0/O`, `1/l/I`, and good ligature-free defaults.

**Decide:** fonts. Recommended: Inter + JetBrains Mono. Alternative: Geist +
Geist Mono (a bit more character, slightly less proven at 12 to 13 px).

### Scale

Base size 14 px (dense app UI), 1.25 ratio for headings. Sizes in rem
(1 rem = 16 px).

| Token     | Size / line height        | Weight | Use                               |
| --------- | ------------------------- | ------ | --------------------------------- |
| `display` | 2.25 rem (36 px) / 1.15   | 600    | Landing page hero only            |
| `h1`      | 1.75 rem (28 px) / 1.2    | 600    | Page title                        |
| `h2`      | 1.375 rem (22 px) / 1.25  | 600    | Section title                     |
| `h3`      | 1.125 rem (18 px) / 1.3   | 600    | Card / panel title                |
| `body`    | 0.875 rem (14 px) / 1.5   | 400    | Default text                      |
| `body-lg` | 1 rem (16 px) / 1.55      | 400    | Landing page, long explanations   |
| `small`   | 0.8125 rem (13 px) / 1.45 | 400    | Table cells, secondary text       |
| `caption` | 0.75 rem (12 px) / 1.4    | 500    | Labels, badges, timestamps        |
| `code`    | 0.8125 rem (13 px) / 1.6  | 400    | SQL blocks and inline code (mono) |

Letter spacing: headings `-0.01em`; `caption` in uppercase only for table
column group labels, `+0.02em`. Numbers in tables and metrics always use tabular
figures. Maximum line length for prose: 70 characters.

Components (0.10.8): `Heading` (level 1 to 3 and `display`), `Text` (`body`,
`body-lg`, `small`, `caption`, plus `muted`), `Code` (inline) and `CodeBlock`
(SQL with syntax highlighting, copy button, line numbers optional).

## 4. Spacing

4 px base unit, using Tailwind's default spacing scale so `p-2` means 8 px.
Allowed steps in product code:

| Step | 1   | 1.5 | 2   | 3   | 4   | 5   | 6   | 8   | 10  | 12  | 16  |
| ---- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| px   | 4   | 6   | 8   | 12  | 16  | 20  | 24  | 32  | 40  | 48  | 64  |

Guidelines: 8 px inside compact controls, 12 to 16 px inside cards, 24 px
between related blocks, 32 to 48 px between page sections. Table rows 36 px high
(compact) or 44 px (comfortable, default for the results table). Page content
max width 1280 px; reading pages (landing, docs) 720 px.

## 5. Radius

| Token         | Value   | Use                                    |
| ------------- | ------- | -------------------------------------- |
| `radius-sm`   | 4 px    | Badges, checkboxes, inline code        |
| `radius-md`   | 6 px    | Buttons, inputs, selects (the default) |
| `radius-lg`   | 10 px   | Cards, dialogs, popovers               |
| `radius-full` | 9999 px | Avatars, pills, toggles                |

Slightly tight radii fit the "instrument" feel; nothing larger than 10 px except
pills.

## 6. Shadows and elevation

Flat by default: surfaces separate by `border` and background, not shadow.
Shadows only for things that float above the page.

| Token       | Light                                                            | Dark                             | Use                           |
| ----------- | ---------------------------------------------------------------- | -------------------------------- | ----------------------------- |
| `shadow-sm` | `0 1px 2px oklch(0 0 0 / 0.06)`                                  | none (border only)               | Buttons on hover              |
| `shadow-md` | `0 4px 12px oklch(0 0 0 / 0.08), 0 1px 3px oklch(0 0 0 / 0.06)`  | `0 4px 16px oklch(0 0 0 / 0.5)`  | Dropdowns, popovers, tooltips |
| `shadow-lg` | `0 12px 32px oklch(0 0 0 / 0.12), 0 2px 6px oklch(0 0 0 / 0.06)` | `0 12px 40px oklch(0 0 0 / 0.6)` | Dialogs, the command palette  |

In dark mode elevation also lightens the surface one step (`surface` to
`surface-muted`), because shadows barely show on dark backgrounds.

## 7. Motion

Dialogs, menus, tooltips and tabs animate with `tw-animate-css` (the shadcn/ui
standard, pure CSS) at the durations below. Our rules:

| Token         | Duration | Easing                       | Use                                            |
| ------------- | -------- | ---------------------------- | ---------------------------------------------- |
| `motion-fast` | 120 ms   | ease-out                     | Hover, press, focus, toggles                   |
| `motion-base` | 200 ms   | `cubic-bezier(0.2, 0, 0, 1)` | Menus, popovers, tabs, toasts                  |
| `motion-slow` | 320 ms   | `cubic-bezier(0.2, 0, 0, 1)` | Dialogs, panels sliding in, page-level reveals |

- Motion explains a change (where something came from, what is loading); it never
  decorates. Nothing loops except progress indicators.
- Agent steps stream in with a short fade and 4 px rise (`motion-base`), so a
  replayed trace reads as a sequence.
- `prefers-reduced-motion: reduce` turns movement into plain fades of 80 ms or
  less (set globally in `index.css`).
- No animation blocks input: a dialog's buttons work before its entrance ends.

## 8. Iconography (Hugeicons)

- Library: `@hugeicons/react` with `@hugeicons/core-free-icons`, the only icon
  source. One style throughout: **stroke rounded**, 1.5 px stroke.
- Sizes: 16 px inline with `small` / `body` text, 20 px in buttons and nav,
  24 px for empty states and page headers. Icons inherit `currentColor`.
- An icon-only button always has an accessible label (and a tooltip). Icons next
  to text are `aria-hidden`.
- Icons support words, they don't replace them: status badges carry text
  ("Passed", "Low confidence"), not only a coloured icon.
- A small wrapper (`<Icon icon={...} size="sm|md|lg" />`) in `src/components/ui/`
  fixes sizes and stroke so feature code never sets them by hand.

## 9. Light and dark themes

Both themes are first-class; every token above has both values. The default
follows the system setting; the toggle (0.10.10) offers System, Light and Dark
and stores the choice in a persisted Zustand store. The theme is applied with a
`class="dark"` on `<html>`, set before first paint to avoid a flash.

## 10. Voice for UI copy

- **Plain and specific.** "Run query", not "Execute". "We couldn't reach the
  database", not "An error occurred".
- **Sentence case** everywhere: buttons, headings, menu items ("Sign in with
  Google", "Eval results").
- **Say what happened and what to do next.** "Your session expired. Sign in again
  to continue." Every error message has a next step.
- **Be honest about the model.** "The model is 62% confident in this answer",
  "This SQL was edited by you before it ran". Never overstate certainty.
- **Numbers with units and context.** "1,204 rows in 0.8 s", "Accuracy 71% (base
  model 64%)".
- **No blame, no jokes in errors**, no exclamation marks, no "Oops".
- **Buttons are verbs** naming the outcome ("Create workspace", "Approve and run"),
  and destructive ones name what they destroy ("Delete workspace").
- Address the user as "you"; Querylab speaks as "we" only in errors and emails.
- Dates in tables as `2026-10-17 17:30`; elsewhere relative ("3 minutes ago")
  with the exact time on hover.

## 11. Accessibility baseline

- WCAG 2.2 AA: contrast as in 2.1, visible focus ring (2 px `primary`, 2 px
  offset) on every interactive element, never removed.
- Everything works by keyboard; dialogs trap focus and return it on close
  (Radix handles this).
- Hit targets at least 32 × 32 px (24 px minimum for dense table actions, with
  spacing).
- Status is never colour alone (text or icon too); charts have labels.

## 12. Components in scope for step 0 (0.10.9)

Plain shadcn/ui components (Radix + Tailwind), themed with the tokens
above, each shown in every state on `/design`: button (primary, secondary,
ghost, destructive, link; sizes sm/md; loading and disabled), input, label,
form (react-hook-form + Zod messages), card, dialog, dropdown-menu, table,
tabs, badge (neutral, success, warning, danger, info), toast (sonner), skeleton,
avatar, separator, tooltip.

---

## Summary of decisions to approve

1. Overall direction (sections 1, 4 to 11) as written.
2. **Accent:** indigo-blue (recommended) / teal / violet.
3. **Fonts:** Inter + JetBrains Mono (recommended) / Geist + Geist Mono.
4. **Base text size:** 14 px (recommended for a dense data app) / 16 px.
5. **Neutral:** warm stone (recommended) / cool zinc.
