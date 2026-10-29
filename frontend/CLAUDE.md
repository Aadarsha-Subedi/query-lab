# Frontend: CLAUDE.md

Vite + React 19 + TypeScript (strict) for Querylab. Static build, served from
Cloudflare on the same domain as the API in production.

## Commands

| Task                                               | Command                             |
| -------------------------------------------------- | ----------------------------------- |
| Dev server (in Docker, with the rest of the stack) | `make dev` from the repo root       |
| Tests (Vitest + React Testing Library)             | `pnpm test` / `pnpm test:watch`     |
| Lint (ESLint, type-aware)                          | `pnpm lint`                         |
| Types                                              | `pnpm typecheck`                    |
| Format                                             | `pnpm format` / `pnpm format:check` |
| Production build                                   | `pnpm build`                        |

## Layout

```
env.config.ts        dev-server env schema (DEV_SERVER_PORT, API_PROXY_TARGET) + proxied paths
env.test.ts          .env.example must list exactly the keys the code reads
vite.config.ts       React, Tailwind, @ alias, dev proxy (/api, /_allauth, /accounts -> Django)
vitest.config.ts     jsdom tests (no dev-server env needed)
components.json      shadcn/ui config (`pnpm dlx shadcn add <name>` adds a component)
src/
  env.ts             Zod schema for import.meta.env; parseEnv()
  EnvErrorScreen.tsx shown instead of the app when env is invalid
  main.tsx           boot: validate env -> /design (dev only) or App, or the error screen
  App.tsx            placeholder until routing (0.10c)
  styles/tokens.css  every design token (light + dark); the only place colours are defined
  index.css          Tailwind, fonts, tokens -> Tailwind theme (@theme inline), base styles
  lib/utils.ts       cn() for class names (tailwind-merge taught our type scale)
  components/ui/     base components (button, input, form, dialog, table, ...) - features import from here
  components/typography/  Heading, Text, Code, CodeBlock
  stores/theme.ts    theme preference (Zustand, persisted); index.html applies it before first paint
  features/design/   DEV-ONLY /design showcase and the switchable design options
  test/setup.ts      jest-dom matchers, stubs for matchMedia, ResizeObserver, Element.animate
build.test.ts        a production build must not contain the /design page
docs/design-system.md   the design system; approved before any UI is built
```

Planned (0.10c): `src/routes/` with `(public)` and `(app)` groups,
`src/features/<feature>/`, `src/stores/`.

## Conventions and rules

- `main` is protected; work happens on branches; Conventional Commits. Claude commits locally only; Aadarsha reviews and pushes.
- **No fallback env values.** Every variable is required and validated with Zod (`src/env.ts`, `env.config.ts`). A new variable goes into the schema and `.env.example` together; `env.test.ts` fails otherwise.
- **No magic numbers.** Timeouts, limits and sizes go into `.env` (and the schema), never inline.
- **State rule:** server data (user, health, later runs) lives in TanStack Query; UI-only state (theme, sidebar, modals) lives in Zustand. Never copy server data into Zustand.
- **Route guard rule:** guards run in the router's `beforeLoad` using the `/api/me` query: signed in on a public route -> `/app`; signed out on an app route -> `/`.
- **Use the design system, never ad-hoc styles.** Colours, spacing, radius, shadows and motion come from tokens; components come from `src/components/ui/`. No raw hex values or one-off pixel sizes in feature code.
- Icons: Hugeicons only, always through `<Icon icon={...} size="sm|md|lg" />` from `components/ui/icon`.
- Toasts: render `<Toaster />` once; call `toast` from `components/ui/toast-api`.
- Design showcase: `pnpm dev`, then open `/design` (dev only; `build.test.ts` checks it never ships).
- Package manager: **pnpm** only (`packageManager` in package.json; `pnpm-lock.yaml` is the lockfile). Never run npm or yarn here: mixing them breaks node_modules.
- UI components are plain shadcn/ui (Radix + Tailwind), adapted to our tokens. After `shadcn add`, replace its Lucide icons with `<Icon>` (Hugeicons), import `cn` from `@/lib/utils`, and keep the variant names used on `/design`. Animations come from `tw-animate-css` with our `duration-*` tokens.
- Don't skip or disable failing tests; fix the cause.
