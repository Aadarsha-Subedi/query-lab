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
