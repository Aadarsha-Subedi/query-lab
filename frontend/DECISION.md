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

## Draft decisions switchable on `/design`

While the design system is finalized, the four open choices (accent, fonts, base
size, neutral) are `data-*` attributes on `<html>` that `tokens.css` reacts to,
set by a dev-only control panel and remembered in localStorage. Once chosen,
the chosen values become the only ones and the switch goes away, together with
the unused font packages.

## `/design` without the router (for now)

Routing arrives in 0.10c. Until then `main.tsx` renders the showcase when
`import.meta.env.DEV` is true and the path is `/design`, through a dynamic
import; production builds drop the branch and the chunk. `build.test.ts` builds
for production and fails if the page is in the output.

## Self-hosted fonts

`@fontsource` packages, bundled by Vite: no request to Google at runtime and no
third-party font CDN. JetBrains Mono's ligatures are switched off so SQL reads
exactly as typed (`>=` stays `>=`).

## Small SQL highlighter, no shiki

`CodeBlock` colours keywords, strings and numbers with a few lines of regex.
Shiki would be far heavier for a single language; revisit if we need more.

## Toasts: sonner

The toast library shadcn recommends; small, accessible, themed with our tokens.
