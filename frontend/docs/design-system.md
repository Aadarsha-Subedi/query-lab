# Querylab design system

Status: **final** (approved by Aadarsha on 2026-10-30). Implemented in
`src/styles/tokens.css` (every token), `src/index.css` (Tailwind theme, fonts,
base styles) and `src/components/` (typography and shadcn/ui components), and
shown in every state on the dev-only `/design` page.

Decisions: **black** primary, **Geist + Geist Mono**, **16 px** base text,
**cool zinc** neutrals; data states and the boot screen (sections 13 and 14)
approved on 2026-10-30. Changes since the first draft: Animate UI was dropped
for plain shadcn/ui (owner's choice); light `muted-foreground` is a 70/30 mix
of the 500 and 600 neutral steps, because the 500 step alone measured 4.39:1
on `surface-muted`, below AA.

Changing anything here means changing the tokens and `/design` in the same
commit.

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
illustrations in the app, no animation that delays reading. The one exception is the landing page's hero: a soft
neutral glow made from `primary-subtle` behind the page, never on a surface.

## 2. Colour

Neutral base: a cool grey (Tailwind's **zinc**), crisp next to black and
neutral under data colours. The primary is **black** (decided by
Aadarsha, 2026-10-29): near-black in light mode, inverted to near-white in dark
mode. It keeps every colour on the page for meaning: the green/amber/red/blue
status colours and the chart palette. Neutral values refer to the zinc scale
in `tokens.css` (`n-0` to `n-950`, OKLCH); hex values are approximate.

### 2.1 Semantic tokens

Components only ever use these names, never a raw colour.

| Token                | Use                                        | Light                           | Dark                            |
| -------------------- | ------------------------------------------ | ------------------------------- | ------------------------------- |
| `background`         | Page                                       | `n-50` ≈ #fafafa                | `n-950` ≈ #0f0f12               |
| `foreground`         | Body text                                  | `n-900` ≈ #18181b               | `n-100` ≈ #f4f4f5               |
| `surface`            | Cards, panels, table body                  | `n-0` #ffffff                   | `n-900` ≈ #18181b               |
| `surface-muted`      | Table headers, code blocks, sidebars       | `n-100` ≈ #f4f4f5               | `n-850` ≈ #1f1f23               |
| `border`             | Dividers, inputs, card edges               | `n-200` ≈ #e4e4e7               | 70% `n-700` + `n-800` ≈ #38383e |
| `muted-foreground`   | Secondary text, captions, placeholders     | 70% `n-500` + `n-600` ≈ #6a6a73 | `n-400` ≈ #9f9fa9               |
| `primary`            | The main action, links, focus ring         | `n-950` ≈ #0f0f12               | `n-50` ≈ #fafafa                |
| `primary-foreground` | Text on primary                            | `n-0` #ffffff                   | `n-950` ≈ #0f0f12               |
| `primary-subtle`     | Selected rows, active nav item background  | `n-200` ≈ #e4e4e7               | `n-800` ≈ #27272a               |
| `success`            | Correct answer, healthy check, passed eval | `oklch(0.56 0.13 152)` #1f8a4c  | `oklch(0.72 0.14 152)` #4cc27a  |
| `warning`            | Low confidence, needs approval, degraded   | `oklch(0.66 0.15 70)` #c4800f   | `oklch(0.79 0.14 75)` #e8ad3c   |
| `danger`             | Errors, failed eval, destructive actions   | `oklch(0.55 0.2 27)` #d12f2f    | `oklch(0.7 0.17 25)` #f26d63    |
| `info`               | Neutral notices, "the model is thinking"   | `oklch(0.58 0.11 230)` #2b86c0  | `oklch(0.74 0.11 230)` #5cb5e8  |

Each status colour also gets a `-subtle` background (about 10% strength) and a
`-foreground` text colour for badges and alerts.

Contrast targets: body text and `muted-foreground` at least 4.5:1 on
`background` and `surface`; `primary` text on `surface` at least 4.5:1; focus
rings at least 3:1 against what they surround; form-control borders are shadcn's own light `input` token (`n-200`; white at 15% in dark), a deliberate choice of the owner over WCAG 1.4.11's 3:1 for field edges (the focus ring and the typed text carry the state). `/design` computes every pair
live; the lowest text pair is 5.0:1.

### 2.2 Data colours (charts, step 4 and the eval dashboard)

Eight categorical colours that stay distinguishable for the common forms of
colour blindness and work on both themes: blue, orange, teal, magenta, olive,
purple, cyan, brown (exact values in 0.10.7, validated with a simulator). A
sequential scale (single-hue blue) for heatmaps and a diverging scale
(red to blue through neutral) for "worse / better than baseline". Charts never
rely on colour alone: values are labelled or shown on hover.

With a black primary, links are always underlined (colour alone no longer marks
them), and the focus ring has a 2 px gap in the background colour so it stays
visible around a black button. The live check on `/design` found every text pair
at 5.0:1 or better in both themes.

## 3. Typography

Two families, both self-hosted through `@fontsource` packages (no request to
Google at runtime, works offline, no layout shift with `font-display: swap` and
matched fallbacks):

- **Geist (variable)** for the interface: clean, slightly technical, with
  tabular figures (`font-variant-numeric: tabular-nums`) for tables and scores.
- **Geist Mono (variable)** for SQL, column names, IDs and trace payloads, with
  ligatures switched off so SQL reads exactly as typed.

### Scale

Base size 16 px, about 1.25 ratio for headings. Sizes in rem (1 rem = 16 px).
Line heights are whole pixels, so every text row, and every icon centred
against it, lands on the pixel grid.

| Token     | Size / line height         | Weight | Use                               |
| --------- | -------------------------- | ------ | --------------------------------- |
| `display` | 2.5 rem (40 px) / 44 px    | 600    | Landing page hero only            |
| `h1`      | 2 rem (32 px) / 38 px      | 600    | Page title                        |
| `h2`      | 1.5625 rem (25 px) / 32 px | 600    | Section title                     |
| `h3`      | 1.25 rem (20 px) / 26 px   | 600    | Card / panel title                |
| `body-lg` | 1.125 rem (18 px) / 28 px  | 400    | Landing page, long explanations   |
| `body`    | 1 rem (16 px) / 24 px      | 400    | Default text                      |
| `small`   | 0.875 rem (14 px) / 20 px  | 400    | Table cells, secondary text       |
| `caption` | 0.8125 rem (13 px) / 18 px | 500    | Labels, badges, timestamps        |
| `code`    | 0.875 rem (14 px) / 22 px  | 400    | SQL blocks and inline code (mono) |

Letter spacing: headings `-0.01em`; `caption` in uppercase only for table
column group labels, `+0.02em`. Numbers in tables and metrics always use tabular
figures. Maximum line length for prose: 70 characters.

Components: `Heading` (level 1 to 3 and `display`), `Text` (`body`,
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
  source. One style throughout: **stroke rounded**, 1.5 px stroke. The one exception
  is a company's own logo (`src/assets/providers`), on sign-in buttons and AI
  settings, always 20 px and decorative.
- Sizes: 16 px inline with `small` / `body` text, 20 px in buttons and nav,
  24 px for empty states and page headers. Icons inherit `currentColor`.
- **Every button has an icon** next to its label (start by default, `end` for
  "next" and menu chevrons). The `Button` component requires an `icon`, and
  TypeScript rejects a button without one. While a button is loading, a spinner
  takes the icon's place, so its width never changes.
- An icon-only button always has an accessible label (`aria-label` is required
  by the type) and a tooltip. Icons next to text are `aria-hidden`.
- **Crisp rendering:** icons render only at 16, 20 or 24 px, through an explicit
  size class (nothing can rescale them), with an absolute 1.5 px stroke at every
  size, `overflow: visible` so stroke ends are never clipped, and `shrink-0` so
  flex rows never squeeze them. Text line heights are whole pixels, so icons sit
  on whole-pixel rows. Horizontal positions can still fall on a fraction of a
  pixel after text of fractional width; CSS cannot snap those in every layout.
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

- WCAG 2.2 AA: contrast as in 2.1, visible focus ring (2 px `primary` with a
  2 px background-coloured gap) on every interactive element, never removed.
- Everything works by keyboard; dialogs trap focus and return it on close
  (Radix handles this).
- Hit targets: 32 to 36 px with a mouse; 44 px on coarse pointers (`pointer-coarse:`
  raises buttons, inputs, selects, tabs and nav links; checkbox, switch and dialog close
  get a 44 px hit area).
- Reduced motion: overlays fade without sliding or zooming and the spinner pulses; state
  changes still show. Each page's h1 sets the tab title; a skip link jumps to `#main`.
- Status is never colour alone (text or icon too); charts have labels.

## 12. Components

Plain shadcn/ui components (Radix + Tailwind), themed with the tokens
above, each shown in every state on `/design`: button (primary, secondary,
ghost, destructive, link; sizes sm/md/icon/icon-sm; always with an icon;
loading and disabled), input, label,
form (react-hook-form + Zod messages), card, dialog, dropdown-menu, table,
tabs, badge (neutral, primary, success, warning, danger, info), toast (sonner), skeleton,
avatar, separator, tooltip, accordion.

## 13. Data states

Every component that reads data from the backend **owns its own loading, error,
empty and success states**. They render inside that component's own box (its
card, panel, table or chart), never as a page-level spinner or error page. If
one component fails, the rest of the page keeps working: the user can still
read, type and use every other feature on it.

### 13.1 Rules

1. **No automatic retries, ever.** A failed request stays failed, whatever the
   status code (TanStack Query `retry: false` for queries and mutations; the API
   client never retries). No refetch on window focus or reconnect either, so
   nothing changes behind the user's back.
2. **The user retries on purpose**: with the component's own **Try again**
   button, which refetches that component's data only (nothing else on the
   page reloads), or by refreshing or hard reloading the page.
3. **One component, one request scope.** A component fetches what it shows. Its
   states never leak out: a failed "Run history" card does not grey out the
   question box next to it.
4. **Same footprint in every state.** Loading, error, empty and success occupy
   the same box size, so nothing on the page jumps when data arrives.
5. **Exceptions that are global by nature:** a 401 (session ended) sends the user
   to sign in, and a 429 also shows a toast with the time to wait. The component
   that got the 429 still shows its own error state.

### 13.2 The four states

| State       | When                                    | Shows                                                                                              |
| ----------- | --------------------------------------- | -------------------------------------------------------------------------------------------------- |
| **Loading** | First load, or after **Try again**      | A skeleton shaped like the real content (rows, lines, bars). `aria-busy="true"` on the component.  |
| **Error**   | The request failed (any status)         | Inline panel: danger icon, what happened, what to do next, a **Try again** button, the request id. |
| **Empty**   | The request worked but there is no data | Neutral icon, what this area will show, and the next step (for example "Ask a question").          |
| **Success** | Data arrived                            | The content itself. Nothing announces success unless the user triggered an action.                 |

### 13.3 Anatomy

**Loading**

- Skeletons, not spinners, for content: a table gets skeleton rows at the real
  row height, a card gets lines at the real text heights. Spinners are only for
  actions the user started (a button's loading state) and the boot screen.
- Skeletons use `surface-muted` with a gentle pulse; with reduced motion the
  pulse stops and the skeleton stays static.
- The component sets `aria-busy="true"` while loading; screen readers hear the
  result once (`aria-live="polite"` on the component's status line), not every
  skeleton.

**Error** (inline, inside the component)

- Danger icon (`AlertCircleIcon`, 20 px) and a one-line title saying what
  happened in plain words: "Couldn't load run history."
- One line saying why, if we know it, and what to do: "The server didn't
  answer. Try again, or refresh the page." For a 429: "Too many requests. Try
  again in 30 seconds." For a 403: "You don't have access to this workspace."
- A **Try again** button (secondary, `RefreshIcon`, per the icon-on-every-button
  rule). While retrying it shows its spinner and the component goes back to its
  loading state.
- The request id in `caption` mono text ("Request 4f1c…"), copyable, so a bug
  report can point at the exact log line.
- `role="alert"` on the error panel so it is announced once.
- Never a raw error, stack trace or status code alone; no "Oops", no blame.

**Empty**

- Neutral icon (24 px, `muted-foreground`), a title naming what will appear
  ("No runs yet"), one line on how to get there, and at most one action button.

**Success**

- Just the content. When the user caused the change (saved, deleted, ran a
  query), confirm with a toast; passive loads never toast.

### 13.4 Actions (mutations)

- The button that started the action shows its loading spinner and is disabled;
  the rest of the component stays usable.
- A failed action is shown next to where it happened: form field errors under
  the fields, other errors as an inline message in the form or component, plus
  an error toast when the user may have scrolled away. The user resubmits; we
  never resubmit for them.

## 14. Boot screen

The one global loading state: shown **only on the first load of the page**,
while the app starts (env check, then the `/api/me` sign-in check, then the
first route). It never appears again during navigation; after boot, every
loading state belongs to a component (section 13).

- **What it shows:** the page background, the Querylab wordmark centred, and a
  small spinner under it with "Loading Querylab" for screen readers. Nothing
  else: no tips, no progress percentages.
- **Theme:** it follows the stored light/dark preference from the first frame,
  because it is plain HTML and CSS in `index.html` that renders before any
  JavaScript runs.
- **No flash on fast loads:** the spinner fades in only after a short delay
  (`boot-delay`, 200 ms), so a fast boot shows a calm blank page for an instant
  instead of a flickering spinner. Once the spinner has appeared, it stays for at
  least `boot-min-visible` (400 ms) so it never blinks. Both are design tokens.
- **Leaving:** it fades out over `duration-base` when the first route is ready.
  With reduced motion it disappears without a fade.
- **Boot failure:** if the app cannot start (the API does not answer the
  sign-in check), the boot screen turns into a full-page message: danger icon,
  "Querylab can't reach the server", "Check your connection and reload the
  page", and a **Reload page** button (`RefreshIcon`). This is the only
  full-page error, because nothing on the page can work without the sign-in
  check. A 401 is not a failure: it means signed out, and the public pages load.
