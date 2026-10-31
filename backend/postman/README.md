# Postman: Querylab API (step 3)

`collection.json` (Postman Collection v2.1) covers every endpoint the backend has
after step 3; `environment.json` is the matching *Querylab local* environment.
Sign-in is Google or GitHub only: there are no email/password accounts.

## Use it

1. Start the stack: `make dev` (the backend answers on `http://localhost:8000`).
2. In Postman: **Import** both files, then pick the **Querylab local** environment.
3. Run **2. Current user → Get CSRF cookie and current user** first. It sets the
   `csrftoken` cookie; the collection copies it into `{{csrfToken}}` after every
   response and sends it as `X-CSRFToken` on every write.
4. Run the folders in order, or use the Collection Runner.

## Signed-in requests

OAuth can only finish in a browser. Open `http://localhost:8000/dev/` (local
only), sign in with Google or GitHub, copy the session id from the textarea and
add it to Postman's cookie jar (Cookies → localhost → add `sessionid`). The
provider apps need `http://localhost:8000/accounts/<provider>/login/callback/`
as a redirect URI. *Session*,
*Connected providers* and */api/me* then answer as that user.

## Notes

- `/api/*` answers in Querylab's envelope (`success`, `data`, ...); `/api/health`
  is unwrapped. `/_allauth/*` answers in allauth's shape (`status`, `data`, `meta`).
- The same email through Google and through GitHub is two separate users;
  `/api/me` shows which provider (`providers`).
- *Log out* answers 401: that is allauth saying the session has ended.
- *Start Google/GitHub sign-in* answers with a redirect to the provider. Until the
  OAuth apps exist in `backend/.env`, the provider's error page is expected.
- *6. Agent*: *Start a run* saves `agentRunId`; the run then waits for *Approve*, *Edit* or *Cancel*.
- When an endpoint is added or changed, update this collection in the same commit.
