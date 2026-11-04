# Postman: Querylab API

`collection.json` (Postman Collection v2.1) covers the full backend surface; `environment.json` is the matching *Querylab local* environment. Sign-in is Google or GitHub only: there are no email/password accounts.

## Use it

1. Start the stack: `make up` (or `make dev`). The backend answers on `http://localhost:8000`.
2. In Postman: **Import** both files, then pick the **Querylab local** environment.
3. Run **2. Current user → Get CSRF cookie and current user** first. It sets the `csrftoken` cookie; the collection copies it into `{{csrfToken}}` after every response and sends it as `X-CSRFToken` on every write.
4. Run the folders in order, or use the Collection Runner.

## Folders

| Folder | Covers |
|--------|--------|
| 1. Health and docs | `/api/health`, OpenAPI |
| 2. Current user | `GET /api/me` + CSRF |
| 3. Sign in with Google or GitHub | Provider redirect (finish in a browser) |
| 4. Session | Session and connected providers |
| 5. Ask | One-shot ask, schema browser, LLM keys / AI settings |
| 6. Agent | Start / list / get / SSE / approve / edit / cancel / result / replay / rate |
| 7. Workspaces | CRUD, schema and agent runs scoped to a workspace |
| 8. Workspace imports and SQL | Presigned dump upload, import status, read-only SQL |
| 9. Workbench | Staff-only traces, cases, drafting, evals, compare |
| Log out | End the session |

## Signed-in requests

OAuth can only finish in a browser. Open `http://localhost:8000/dev/` (local only), sign in with Google or GitHub, copy the session id from the textarea and add it to Postman's cookie jar (Cookies → localhost → add `sessionid`). The provider apps need `http://localhost:8000/accounts/<provider>/login/callback/` as a redirect URI. *Session*, *Connected providers* and */api/me* then answer as that user.

For staff workbench requests, the signed-in user must have `is_staff=true` (`make createsuperuser`, or set the flag in a shell).

## Notes

- `/api/*` answers in Querylab's envelope (`success`, `data`, …); `/api/health` is unwrapped. `/_allauth/*` answers in allauth's shape (`status`, `data`, `meta`).
- The same email through Google and through GitHub is two separate users; `/api/me` shows which provider (`providers`).
- *Log out* answers 401: that is allauth saying the session has ended.
- *Start Google/GitHub sign-in* answers with a redirect to the provider. Until the OAuth apps exist in `backend/.env`, the provider's error page is expected.
- *6. Agent*: *Start a run* saves `agentRunId`; the run then waits for *Approve*, *Edit* or *Cancel*.
- *8. Imports*: get an upload URL, `PUT` the dump to R2 yourself, then *Start the import*.
- When an endpoint is added or changed, update this collection in the same commit (and re-run `make openapi`).
