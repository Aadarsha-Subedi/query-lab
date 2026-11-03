# Step 5a: Dump import (replaces CSV import and table editing)

**Goal:** a user sets up a private workspace by uploading a plain-SQL `pg_dump`, then asks questions and runs read-only queries. Nobody edits tables or rows in the app; to change data, upload a new dump (with "Replace data").

**Decisions (owner, 2026-11-02/03):** uploads go browser to Cloudflare R2 with a presigned PUT; boto3 is allowed and the image budget is 400 MB; the file limit is 50 MB; the UI offers data import only, no structure or row editing; the query runner stays but is read-only on the `_ro` role.

**Done when:**

- [x] D.1 boto3 added, botocore trimmed to the S3 model in the Dockerfile; image 305 MB of 400.
- [x] D.2 `R2_*` and `DUMP_*` settings in `.env.example`, `.env.test` and settings.
- [x] D.3 `workspaces/dump.py`: streaming reader. Everything runs as the `_rw` role; only what cannot work here is set aside (server-level statements, transaction control, DROP, row security). `public.` and the dump's own schema names are removed. The first version had a statement allowlist; the owner removed it on 2026-11-03.
- [x] D.4 `workspaces/storage.py`: presigned PUT pinned to the exact size, streamed (gunzipped) read with a decompressed-size cap, delete.
- [x] D.5 `ImportJob` model, `workspaces/importer.py` and the Huey task: one transaction as `_rw`, size caps checked before commit, replace mode, object always deleted.
- [x] D.6 Endpoints `POST/GET /workspaces/{id}/imports`, `.../{job}/start`, `.../{job}`; throttle `workspace_import`; one active import per user.
- [x] D.7 Removed table, column, key, relation and row endpoints; `POST /workspaces/{id}/sql` is read-only and runs as `_ro`.
- [x] D.8 `API_ERRORS.md` updated. `openapi.json` and the Postman collection regenerated in the working tree (committed together with the owner's pending account changes).
- [x] D.9 Frontend: Import tab (file picker, replace, upload progress, manual "Check progress", errors with statement and line), Schema and Query tabs for private workspaces; editors removed. No polling (owner rule).
- [ ] D.10 **(You)** Real R2 bucket: create it, set CORS to allow `PUT` from the app origin, add a 1-day lifecycle rule on `dumps/`, fill `R2_*` in `.env`, then import a real dump.
- [ ] D.11 **(You)** Measure a 50 MB dump on the 0.25 vCPU / 1 GiB container and tune `DUMP_STATEMENT_TIMEOUT_MS`.
