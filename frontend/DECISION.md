# Frontend: DECISION.md

## Vite + React + TypeScript (strict)

A static single-page app: nothing needs server rendering (every page sits behind
login except the landing page), and a static build deploys to Cloudflare for free
on the API's domain. TypeScript `strict` plus `noUncheckedIndexedAccess`; the `@/`
alias points at `src/`.

TypeScript is pinned to `~6.0` (not the 7.x the Vite template ships) because
typescript-eslint supports TypeScript `<6.1`. The template's oxlint was replaced
with ESLint (type-aware `strictTypeChecked`) and Prettier, as planned.

## Tailwind + shadcn/ui + Hugeicons

Tailwind v4 (Vite plugin) for styling through design tokens. Components are plain
shadcn/ui (Radix primitives + Tailwind), generated with the shadcn CLI into
`src/components/ui/` and then adapted: `cn` from `@/lib/utils`, Hugeicons instead
of Lucide, our token classes and type scale, and our variant names (button
primary/secondary/ghost/destructive/link with a `loading` state; badge
neutral/primary/success/warning/danger/info). Enter/exit animations use
`tw-animate-css` (pure CSS) with our `duration-*` tokens; reduced motion is
respected globally. Hugeicons (`@hugeicons/react` + the free set) is the only icon
library, always through the `<Icon>` wrapper.

Lint: the strict type-aware rules that flag shadcn's own patterns (exporting
variant helpers, a few redundant checks) are switched off for
`src/components/ui/**` only, so the files stay close to upstream.

**Animate UI was dropped** (2026-10-29, owner's choice) in favour of plain shadcn/ui.
It had been the plan's component layer on top of shadcn; with it went `motion`
and `@animate-ui/cli`.

## pnpm

The owner's choice (2026-10-29). `packageManager` in package.json pins the
version; corepack provides it in the dev container. `pnpm-workspace.yaml` keeps
the supply-chain exception for `@hugeicons/core-free-icons`. npm's lockfile is
gone; never mix package managers in one `node_modules`.

## TanStack Router + TanStack Query

Typed routes with `beforeLoad` guards and route groups (`(public)`, `(app)`);
Query owns all server state (user, health, later runs) with caching and
refetching. The router's Vite plugin is added with the routes in 0.10c.

## Zustand for UI-only state

Theme, sidebar and modal state only, persisted where useful (theme to
localStorage). Server data never goes into Zustand.

## react-hook-form + Zod

Forms validate with the same Zod schemas the app uses for types.

## Environment: Zod-validated, no fallbacks

`src/env.ts` validates `import.meta.env`; a missing variable shows a hard error
screen. The dev server validates its own variables (`env.config.ts`). `env.test.ts`
keeps `.env.example` in sync with both schemas.

## Dev server in Docker, proxying to Django

The Vite dev server runs in the `frontend` compose service on
`querylab-network` and proxies `/api`, `/_allauth` and `/accounts` to
`API_PROXY_TARGET` (the `backend` service), keeping the browser's Host header.
Cookies are therefore same-origin locally, as they are in production.
`node_modules` lives in a named volume so the host's install is never used in the
container.

## Design system first

`docs/design-system.md` is written and approved before any token, component or
screen is implemented. Showcase: a dev-only `/design` route, not Storybook.

## Tokens as CSS variables, mapped into Tailwind

`src/styles/tokens.css` defines every token for light and dark; `index.css`
maps them into Tailwind with `@theme inline`, so `bg-surface`, `text-h1`,
`rounded-md` and `shadow-md` all read the tokens, and the shadcn names (card,
popover, muted, destructive, ring) point at the same values. Tokens whose name
matches a Tailwind theme key carry a `--ds-` prefix (`--ds-radius-md`), so the
theme never references itself. `cn()` uses `extendTailwindMerge` so our type
scale (`text-h1`, `text-small`, ...) is not dropped as a colour conflict.

## Final design choices (2026-10-30, owner's choice)

Geist + Geist Mono, 16 px base text and cool zinc neutrals, with the black
primary decided the day before. They were compared live on `/design` (each
option was a `data-*` attribute that `tokens.css` reacted to); once chosen,
the alternatives, the option panel and the Inter and JetBrains Mono packages
were removed. `/design` keeps only the light/dark/system toggle.

## `/design` without the router (for now)

Routing arrives in 0.10c. Until then `main.tsx` renders the showcase when
`import.meta.env.DEV` is true and the path is `/design`, through a dynamic
import; production builds drop the branch and the chunk. `build.test.ts` builds
for production and fails if the page is in the output.

## Self-hosted fonts

`@fontsource` packages (Geist and Geist Mono, variable), bundled by Vite: no
request to Google at runtime and no third-party font CDN. Ligatures are switched
off in mono text so SQL reads exactly as typed.

## Small SQL highlighter, no shiki

`CodeBlock` colours keywords, strings and numbers with a few lines of regex.
Shiki would be far heavier for a single language; revisit if we need more.

## Toasts: sonner

The toast library shadcn recommends; small, accessible, themed with our tokens.

## Black primary (2026-10-29, owner's choice)

Primary is near-black in light mode and inverts to near-white in dark mode, so
primary buttons keep their contrast. Colour is reserved for meaning: status
colours and the chart palette are unchanged. Links are always underlined, and the
focus ring is a solid ring with a background-coloured gap so it shows around a
black button. The indigo, teal and violet options are gone from the tokens and
`/design`.

## Every button has an icon; icons render crisp

Owner's rule. `Button` requires an `icon` (start or end) and, for icon-only sizes,
an `aria-label`; TypeScript enforces both (`@ts-expect-error` cases in the
component tests). Loading swaps the icon for a spinner in the same slot, so the
width never changes. `Icon` renders only at 16/20/24 px through a size class (the
shadcn button's own `[&_svg]:size-4` rule had been rescaling 20 px icons and
blurring them), with an absolute 1.5 px stroke, `overflow: visible` and
`shrink-0`. Line heights became whole pixels so icons sit on whole-pixel rows.
Horizontal positions after fractional-width text can still be a fraction of a
pixel; `calc-size()` width rounding was tried and rejected (it re-centres content
by a fraction instead).

## Data states and no retries (2026-10-30, owner's rules)

Every component that reads from the backend owns its loading, error, empty and
success states inside its own box, so one failure never blocks the rest of the
page. Nothing retries automatically, whatever the status code, and nothing
refetches on window focus or reconnect; the user retries with that component's
own Try again (its data only) or by reloading the page. The only global loading
state is the boot screen on first load (plain HTML in index.html, spinner after
200 ms, shown at least 400 ms), and the only full-page error is the boot screen's
"can't reach the server". See design-system.md sections 13 and 14.

## Routing: file routes with pathless layouts (0.10c)

TanStack Router file-based routes. A group needs a layout route to run a guard,
so the plan's `(public)` and `(app)` groups are the pathless layouts `_public`
and `_app` (the underscore keeps them out of the URL). Guards read `meQuery`
through `queryClient.query({ ...meQuery, staleTime: 'static' })`, so the answer
fetched at boot is reused and navigation never re-asks. Route-level code
splitting (`autoCodeSplitting`) keeps the main chunk under 500 kB.

## Boot: sign-in check before the first render

`main.tsx` asks `/api/me` once before rendering, so the boot screen can show
the only full-page error ("can't reach the server") when that fails; a 401 just
means signed out. The boot screen itself is static HTML styled by `tokens.css`
and `boot.css`, both linked from `index.html`, so it is themed from the first
frame; `boot.ts` only times its exit or shows the failure.

## One API client, CSRF from /api/me

`src/lib/api` is the only way to call the backend: cookies included, the
`X-CSRFToken` header on writes, the response envelope unwrapped into data or a
typed `ApiError` (with the request id), a toast on 429, and no retries. Django
sets the `csrftoken` cookie only when asked, so `GET /api/me` (called at every
boot) carries `ensure_csrf_cookie`.

## Step 9: the product screens (2026-11-01)

**Types come from the contract.** `openapi-typescript` (dev only, no runtime weight) writes
`src/lib/api/schema.gen.ts` from `backend/openapi.json`; CI runs `pnpm gen:api:check`. Building on it
found two real backend defects, both fixed (schema classes with the same name merge in
`openapi.json`): the agent and workspace `LimitsOut`, and the agent and eval `ResultOut`. The agent ones are
now `AgentLimitsOut` and `RunResultOut`, and a backend test fails when two schema classes share a name.

**No retries, polling or timers.** The owner's rule: a failed request shows its error and the user reloads
or presses Try again. The live run follows the same rule: the SSE reader (`fetch`, so cookies and
`Last-Event-ID` work; not `EventSource`, which reconnects by itself) opens once, again after approve/edit
(the server closes the stream at the pause), and again only when the user presses Reconnect. `API_ERRORS.md`
suggests polling after `agent_stream_limit`; we show the message and Reconnect instead. `no-retry.test.ts` bans
`retry`, `refetchInterval`, `setInterval`, `setTimeout` (except the boot screen) and `EventSource` in `src/`.

**Staff flag on `/api/me`.** The workbench needed to know who is staff; `GET /api/me` now returns `is_staff`
(additive, tested). The guard and the nav use it; the API still enforces `staff_only`.

**What was left out or changed from the plan.**

- CSV upload: dropped with backend 5.7. Tables are filled through the rows form and the SQL console.
- The workspace picker sits on the ask page, not in the header (the header chip shows the shared key's limit).
- Eval filters in the UI are target and model; runner and prompt version are accepted in the URL only.
- Diff of proposed vs approved SQL is a small inline line diff (no library).
- No chart library: accuracy by cluster is a table with inline bars. Revisit only if a trend over time is wanted.
- The LLM keys page has an optional model text field, because the API has no endpoint that lists allowed models.
- Rows grid page size = the API's `max_rows_per_edit`, so no new `.env` value was needed.
- `column types` and `on delete` choices and the provider names are constants checked against the backend source (`ws-contract.test.ts`).

**Quality checks that run in `pnpm test`.** `states.test.tsx` (every data screen shows a loading box and an error box
with its own Try again and does not retry), `a11y.test.tsx` (axe on every screen, colour contrast off because jsdom has no
layout), `api-errors.test.ts` (every code in `API_ERRORS.md` has wording).

**Sizes (2026-11-01).** `pnpm build`: entry chunk 287 kB (about 93 kB gzip); the largest lazy chunks are the schema/table
library 86 kB, alert-dialog and select 56 kB, and the workspace editor 40 kB. Route-level splitting keeps the workbench and
workspace editor out of the first load. `/design` is still absent from the production build.

**Checked against the running stack (9.11.1).** With a signed-in test session in headless Chrome: the pages load without
errors or horizontal overflow at 375, 768 and 1280 px; a real run reached the approval card, approved, ran, showed the result;
creating a workspace, a table, a row, running SQL and deleting the workspace all worked. Findings fixed: three pending
migrations in the dev database (not a code bug), the schema list clipped by the scroll area, long SQL scrolling under the copy
button, and the ask page order on phones. Not checked: the Google/GitHub sign-in itself, which needs your accounts.

**Impeccable pass (2026-11-01, branch `feat/frontend-impeccable-pass`).** Scored 27/40 on design heuristics and 17/20 on
the technical audit (detector: 0 findings). Fixed: form-control borders to 3:1; 44 px targets on coarse pointers; page
titles from the h1 (done in `Heading`, no router head API) plus a skip link and `<main id="main">`; reduced motion that
fades instead of freezing; one `RunStatusBadge` and one focus ring; a real Home (replaces `PlaceholderPage`; system health
moved to the workbench); guard, revision and limit meanings as always-visible text rather than tooltips (tooltips do not
work on touch); vote copy; Ask again / New question (`/ask?question=`); limits chip invalidated when a run ends; result rows
before SQL; on phones the schema panel now comes after the question box. Not done: an "active key" badge on the keys page
(the API returns no saved-at time, so the UI cannot know which key is used), and a score column in History (needs a backend
field). No new timers or retries were added.

**AI settings page (2026-11-01).** The keys page became "AI settings": a two-option choice (QueryLab AI or My own AI), and for
"own" a fixed two-row table (OpenAI, Gemini) with a model dropdown per saved key, a radio for the one key in use, and Remove,
plus one add-or-replace form whose provider dropdown shows the logos. The choice is saved at once (`PUT /api/llm-settings`).
With "own" and no key in use the page says questions are paused and the backend refuses them (`no_active_key`): no quiet
fallback to QueryLab's key. The "In use" column sits before "Model" so the radio stays on screen on phones. The OpenAI logo
is black on transparent, so it is inverted on the dark theme. Radix Select needs pointer-capture stubs in `test/setup.ts`.

**AI settings layout revised (2026-11-01).** Owner's pattern: title and description on the left, the choice as a dropdown on
the right (QueryLab AI or Custom AI). The key table appears only for Custom AI and lists saved keys only (no "No key" rows).
With no keys it shows an empty state with one Add new API key button; adding and replacing a key happen in a modal
(`AddKeyDialog`), never inline. Once a key exists, the same button sits beside the heading until both providers have one; each
row has Replace and Remove. A modal is used here because the key is a secret that needs focused entry, at the owner's request.

**No page headers on Workspaces and AI settings; route is /settings (2026-11-01).** The nav item already names the page, so the
visible h1 is gone on these two. The h1 stays as `sr-only` text because it names the browser tab (see `Heading`) and gives screen
readers a page heading. The keys route moved from `/settings/keys` to `/settings`. Workspace cards no longer carry buttons: Ask,
Edit tables and Delete workspace sit in one actions menu per card (the demo only offers Ask), and Delete still needs the typed
name; `DeleteWorkspaceDialog` is now opened by the menu instead of its own trigger.

**Model choice on QueryLab AI (2026-11-01).** With QueryLab AI selected, a second setting row (title and description left,
dropdown right, like the AI source row) lets the user pick which Gemini model answers on the shared key. The list is the same
`LLM_GEMINI_MODELS` allowlist served by `/llm-keys-models`. It is hidden for a custom AI, which has its own model per key.

**Ask and Schema as sub-tabs, table details in a modal, field styling (2026-11-01).** The schema browser no longer sits in a
narrow side column: `/ask` has two sub-tabs (`?tab=schema`; Ask is the default and leaves the URL clean) under one workspace
picker, so each gets the whole width. The per-table info button opens a dialog instead of a slide-in sheet. The Querylab mark
(`src/assets/logo.svg`) is the favicon and the topbar logo (it flips to a white tile on the dark theme). Form fields use the
`surface` colour with `--input` at `n-450` (about 3.4:1), the lightest grey that still passes WCAG 1.4.11; the earlier `n-500`
made every field look heavy next to the light cards. Rows of the shared demo tables are still not viewable (no endpoint); the
structure, columns, keys and samples are, on the Schema tab.

**Table view and chat-style Ask (2026-11-01).** On the Schema tab, picking a table shows it as a table: a metadata block (description, size,
primary and foreign keys, column notes), column headers that carry the type and PK/FK badges, and a read-only page of its rows from
the new `GET /api/schema/tables/{name}/rows` (demo and private workspaces alike; paging is manual, no prefetch). This replaced the
expand-in-list and the info-button modal (and the Zustand expand store). The chosen table is in the URL (`?table=`). The Ask tab is
a chat: the conversation (or a short prompt before the first question) above, a sticky composer below with the example questions
over it; the Ask button is gone, a send icon sits inside the text box, and Enter sends (Shift+Enter for a new line), as in an LLM chat.

**Reasoning view and plain-language steps (2026-11-01).** While a run works, `Reasoning` shows what the agent is doing as a
shimmering stage line with its notes fading in below and the tables it read as sources; it takes `stages`, `reasoning`, `sources`,
`active` and `className`. The Animate UI style also has `stageMs`, `reasonMs` and `onDone` to pace the animation; they are left
out on purpose because pacing needs timers, which are banned (`no-retry.test.ts`). The real step events pace it instead. The
shimmer is a CSS animation (not a JS timer) and stands still under reduced motion. `step-text.ts` turns each step into a stage
and a note in plain words (`describe_table` becomes "Reading the orders table", `reflect` becomes "Looks right. ..."), so raw
JSON never reaches the screen: unknown JSON is dropped, plain text is kept. The same text feeds `RunTimeline` (finished runs,
Replay and the staff trace view). The Ask column is `--chat-max` (768 px) and centred.

**Ask trimmed to a chat (2026-11-01).** The user's question is a right-aligned bubble, not a heading, and carries no status tag
(the status is still announced to screen readers; cancelled and expired runs say so in one muted line). The collapsed "What the
agent did" list and the Ask again / New question buttons are gone from the Ask page: History already has the replay and an Ask
again link. The thumbs are plain icons with no background; the chosen one is darker and bolder, so the state does not rely on a
fill. `RunTimeline` remains for Replay and the staff trace view.

**Schema table view trimmed (2026-11-01).** The table's size and column count, the Primary key / Foreign key text and the
"Column notes" list are gone: the column headers already show type and PK/FK badges, and each header has an info button whose
popover holds that column's notes, primary key and foreign key target. A popover rather than a modal, because it explains one
column in place; it uses `sticky="always"` so it stays on screen when the column is scrolled partly out of view.

**No Home page; Ask is the default (2026-11-01).** The Home screen (ask button, how it works, recent questions) is gone: signing
in lands on `/ask`, the brand link goes there, and the nav starts with Ask. History already lists recent questions. The skip
link and `<main id="main">` convention stay. The Workspaces card is one big link (the workspace name, stretched over the card)
that opens that workspace's Schema tab (`/ask?tab=schema&workspace=<id>`, no `workspace` for the demo); the actions menu stays
clickable above it.

**Select is shadcn base-nova (Base UI) (2026-11-02).** The owner pointed out that our Select was the Radix "new-york" one and looked
out of place beside shadcn's current Select. `components/ui/select.tsx` is now the base-nova source (Base UI, new dependency
`@base-ui/react`), with Hugeicons (up/down chevrons, check) and our tokens, heights (36 px, 44 px on touch) and focus ring. Base UI
shows the raw value in the trigger unless it is given `items`, so our `<Select>` derives them from its `<SelectItem>` children and
passes `onValueChange` the string only; the 19 call sites did not change. Input and textarea moved to the same `rounded-lg`
radius. The other components are still Radix (new-york); `components.json` was left on new-york. Moving them to base-nova is a
separate, larger change.

**Stock shadcn fields, no extra styling (2026-11-02).** The Select still showed a dark border: it came from our own `--input` token (the
3:1 contrast fix). The owner asked for plain shadcn, so `select.tsx`, `input.tsx` and `textarea.tsx` are now the base-nova sources
verbatim (only the icons are Hugeicons, plus the `<Select>` root's label and string-value convenience), and `--input` is shadcn's own:
`n-200` in light, white at 15% in dark. This undoes my earlier WCAG 1.4.11 border fix and the 44 px touch height for fields
(stock is 32 px, `rounded-lg`, transparent fill); the owner accepted that trade. Select triggers that sat in a fixed-width box
got `w-full` at the call site, because the stock trigger is `w-fit`.

**Top bar, profile menu and usage (2026-11-02).** The workspace picker moved into the top bar (on the Ask page only: that is where
`?workspace=` applies; it shows nowhere else, and changing it drops the open run and table). The theme choice moved into the
profile menu (Light, Dark, System as radio items, above Sign out) and the theme button left the bar. The usage chip left the bar
too: its details are a Usage section on the AI settings page (`UsageSection`). The avatar button and the line before the email show
the provider's picture (`avatar_url` from `/api/me`, loaded from the provider directly, initials as the fallback).

**shadcn AI elements (2026-11-02).** At the owner's request the Ask page is built from the shadcn AI elements (base-nova, Base UI), added as
`components/ui/{collapsible,trace,message,bubble,message-scroller,input-group,item,code-block}.tsx` (new dependency `@shadcn/react` for the
Message Scroller). What replaced what: Prompt Input (Input Group) for the question box; Message, Bubble and Message Scroller for the thread;
Suggestion for the example questions; Reasoning (on Trace) for the live "thinking" line; Confirmation (on Item) for the SQL approval, with
our SQL editor kept inside; Chain of Thought and Tool (on Trace) for `RunTimeline` in Replay and the staff trace view; Code Block for SQL.
Left out on purpose: Context (it counts tokens; our Usage counts questions), Model Selector (maybe later), Sources, Checkpoint, File Tree,
Inline Citation, Queue, Stack Trace, Subagent, Task, Terminal, Test Results. Adaptations: Hugeicons instead of the placeholder icons; the Input
Group has no `InputGroupButton` (our `<Button icon>` is used directly, because every button has an icon); the Code Block copy button has no
two-second timer (this app has none): the check clears when the pointer or focus leaves it; the `shimmer`, `scrollbar-thin`,
`scrollbar-gutter-stable` and `scroll-fade-*` utilities the components expect are defined in `index.css`, and the shimmer holds still under
reduced motion. The Message Scroller package follows the reply with its own animation frames; that is scrolling, not a retry or a poll.

**Selects inside dialogs (2026-11-02).** The provider and model lists in "Add new API key" closed the moment they opened: the Radix
dialog traps focus and treats anything outside itself as an outside click, and the Base UI Select list was portalled to the page body.
`DialogContent` now hands its own element to the Select through `PortalContainerContext` (`components/ui/portal-container.ts`), so the
list renders inside the dialog, and inside a dialog the list uses normal placement (`alignItemWithTrigger` off), because the
align-over-trigger maths assumes page coordinates and the dialog is a transformed box. Every dialog with a select (AI keys, create
table, columns, row editor) gets this for free.

**Usage as shadcn Progress; suggestions wrap (2026-11-02).** shadcn has no "usage limit" component of its own: its AI Elements "Context"
shows usage with Progress, so the Usage section on AI settings uses `components/ui/progress.tsx` (Base UI Progress, base-nova source): one row
each for questions on the shared key today, open questions and live views, with a label, "used of allowed" and a bar that turns red at 90%.
The daily reset time sits under its row, and a custom-AI user sees "No daily limit from us". The example questions on Ask are no longer
a sideways-scrolling row: they wrap onto new lines and each one wraps its own text, so none is cut off.

**Sticky sidebar (2026-11-02).** The desktop sidebar is `sticky top-14` with the height of the screen under the top bar, so it stays in view when a long page scrolls (the top bar was already sticky). On phones the nav is a sheet, unchanged.

**Workspace editor layout (2026-11-02).** The editor was a loose column of controls on the left edge of the page. It is now centred (`--content-max`) and
arranged like a database console (Neon's, for example) from our shadcn components: a breadcrumb back to Workspaces, the workspace name and
description with its storage as a shadcn Progress on the right, line tabs (Tables, Relations, SQL console), and for Tables one bordered panel split
in two: the table list with New table on the left, and the selected table on the right (name and description fields with Save and Drop in the header,
then Columns and Rows as line tabs). Relations and the SQL console sit in a bordered panel too. No behaviour or API changed.

**The workspace editor lives in Ask (2026-11-02).** Editing a private workspace needed Workspaces, then the card, then Edit tables. Now the workspace picker in the top bar
chooses it and the Ask page grows the editor as tabs: Ask, Tables, Relations, SQL console (the shared demo keeps Ask and Schema). Tables is the editable
version of the Schema view (columns, keys, rows), so a private workspace has no separate Schema tab (an old `?tab=schema` link opens Tables, and an editor tab on the
demo opens Schema). Storage is a Progress at the right of the tab row. The Workspaces page is the list (create, open, delete); its card and "Edit tables" open the
Tables tab. `/workspaces/$id` stays as a redirect so old links work; `WorkspaceDetail` is gone. The editor tabs scroll with the page and are centred at `--content-max`;
only the Ask tab (the chat) fills the screen and scrolls inside itself.

**History row actions (2026-11-02).** Replay and Ask again are secondary small buttons with icons (Play, Reload) instead of text links, like every other action. They are still links underneath, so open-in-new-tab and middle-click work.

**Dump import UI (2026-11-03).** Owner decision: users analyse, they do not edit. The Tables and Relations tabs and every editor (create table, columns, rows, keys, relations) were removed; the Import tab and a read-only Query tab replace them. The Import tab is a panel, not a dialog (it is a task, not an interruption). Uploads use `XMLHttpRequest` because `fetch` cannot report upload progress; this is not a timer or a poll. The job status is read once after `start` and again only when the user presses "Check progress", because the owner's rule forbids polling (`no-retry.test.ts`). The size limit comes from `GET /workspaces/limits` (`max_dump_bytes`), never a constant. Types come from the regenerated `schema.gen.ts`.

**Import and Query moved into Schema (2026-11-03, owner).** The Import and Query tabs are gone. A private workspace's Schema page has an Import dump button (a popup with the upload form and a table of past imports) and the read-only Query terminal under the tables. Ask and Schema are the only tabs for every workspace; old `?tab=import` / `?tab=sql` links open Schema. Private workspace storage is 50 MB (`WORKSPACE_MAX_BYTES`).

**Workspace menu (2026-11-03, owner).** The Schema page of a private workspace has one three-dots menu instead of loose buttons: View storage capacity (a modal; the inline storage bar in the tab row is gone), Import dump (the existing popup) and Run query (a right-hand sheet, wide on desktop). The query text lives in a persisted Zustand store keyed by workspace id (UI-only state, not server data), so closing the sheet or reloading keeps it; the results are not kept.

**No statement restrictions on a dump (2026-11-03, owner).** The Import popup's command is plain `pg_dump mydb | gzip`, with no required flags, and its copy no longer lists refused statement types. See backend DECISION.md.
