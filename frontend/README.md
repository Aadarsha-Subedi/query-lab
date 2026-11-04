# Frontend

Vite + React 19 + TypeScript for Querylab. In production the static build is served by the backend's Cloudflare Worker on the same origin as the API.

## Run it

From the **repo root**:

```bash
make setup && make up   # Vite on :3000, proxies /api /_allauth /accounts → Django
```

Or inside this folder with the stack already up: `pnpm install && pnpm dev`.

| Task | Command |
|------|---------|
| Tests | `pnpm test` / `make test-frontend` |
| Lint / types / format | `pnpm lint` · `pnpm typecheck` · `pnpm format` |
| API types from `../backend/openapi.json` | `pnpm gen:api` (CI: `gen:api:check`) |
| Production build | `make build-frontend-prod` from the repo root (sets the live origin). Do not use plain `pnpm build` for deploy — it would bake in `localhost` from `.env`. |

Copy `.env.example` → `.env`. Every variable is required (Zod at boot).

## Layout

```
src/
  routes/           TanStack file routes: landing, login, ask, history, workspaces, settings, workbench, privacy/terms
  features/         per-screen queries + UI (ask, workspaces, workbench, landing, …)
  lib/api/          envelope client, CSRF, generated OpenAPI types
  components/ui/    design-system primitives
  styles/tokens.css every colour / motion token (light + dark)
docs/design-system.md
```

Dev-only design showcase: `/design` (stripped from production builds).

## Docs in this folder

| File | What it is |
|------|------------|
| [`CLAUDE.md`](CLAUDE.md) | Commands, layout, hard rules |
| [`FLOW.md`](FLOW.md) | Boot, routes, data fetching, sign-in |
| [`DECISION.md`](DECISION.md) | UI / contract choices |
| [`docs/design-system.md`](docs/design-system.md) | Tokens, components, data states |

Package manager is **pnpm** only. Types come from the backend OpenAPI schema (`Schema<'Name'>`); never hand-write response shapes. No automatic retries, polling, or `EventSource` — the user retries or reconnects.
