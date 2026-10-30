# Postman: Querylab API (step 0)

`collection.json` (Postman Collection v2.1) covers every endpoint the backend has
after step 0; `environment.json` is the matching *Querylab local* environment.

## Use it

1. Start the stack: `make dev` (the backend answers on `http://localhost:8000`).
2. In Postman: **Import** both files, then pick the **Querylab local** environment.
3. Fill in `email`, `password` and `newPassword` in the environment. They are
   empty or placeholders in the committed file; never commit real values.
4. Run **2. Current user → Get CSRF cookie and current user** first. It sets the
   `csrftoken` cookie; the collection copies it into `{{csrfToken}}` after every
   response and sends it as `X-CSRFToken` on every write.
5. Run the folders in order, or use the Collection Runner.

## What sends email

*Sign up*, *Email verification: resend*, *Change password* and *Request password
reset* send real email through the SMTP settings in `backend/.env`. Paste keys
from those emails into the environment:

- `verificationKey`: from the link `.../verify-email/<key>` (URL-decoded)
- `resetKey`: from the link `.../reset-password/<key>` (URL-decoded)

## Notes

- `/api/*` answers in Querylab's envelope (`success`, `data`, ...); `/api/health`
  is unwrapped. `/_allauth/*` answers in allauth's shape (`status`, `data`, `meta`).
- *Log out* answers 401: that is allauth saying the session has ended.
- *Start Google/GitHub sign-in* only finishes in a browser (it redirects to the
  provider). Until the OAuth apps exist, the provider's error page is expected.
- 6 failed logins in a row on one address give `too_many_login_attempts`
  (RATE_LIMIT_LOGIN_FAILED).
- When an endpoint is added or changed, update this collection in the same commit.
