# Backend: API error codes

Every error answers in the envelope `{success: false, status_code, message, code, errors: [{field, message}]}`; a 429 also has `retry_after_seconds` (and a `Retry-After` header). The screen branches on `code`, never on `message`. The test `common/tests/test_error_list.py` fails when an `AppException` subclass has no row here, or a row names a code the code no longer has. Keep the tables in the format below: one row per code, the code in backticks in the first column.

## API errors (HTTP responses)

| Code | HTTP | Meaning | What the screen does |
|------|------|---------|----------------------|
| `authentication_denied` | 401 | Not signed in (or the session ended). | Go to sign-in. |
| `invalid_token` | 401 | A token was invalid (not used by the browser flow). | Go to sign-in. |
| `token_expired` | 401 | A token expired (not used by the browser flow). | Go to sign-in. |
| `permission_denied` | 403 | Signed in but not allowed (also a failed CSRF check). | Reload to get a fresh CSRF cookie via `GET /api/me`, then retry once. |
| `staff_only` | 403 | The workbench (`/api/workbench/...`) is for staff accounts only. | Hide the workbench; show "not available". |
| `not_found` | 404 | No such route or resource. | Show "not found". |
| `method_not_allowed` | 405 | Wrong HTTP method for the route. | A bug in the client. |
| `unsupported_media_type` | 415 | Body was not JSON. | A bug in the client. |
| `bad_request` | 400 | The request was malformed. | Show the message. |
| `validation_error` | 400 / 422 | A field is missing or invalid; `errors` names the fields. | Show each `errors[].message` next to its `field`. |
| `unprocessable_entity` | 422 | Well formed but not acceptable. | Show the message. |
| `conflict` | 409 | Generic state conflict. | Reload the resource. |
| `duplicate_resource` | 409 | The resource already exists. | Show the message. |
| `stale_data` | 409 | The resource changed since it was read. | Reload, then retry. |
| `resource_locked` | 423 | The resource is locked. | Retry later. |
| `payload_too_large` | 413 | Body too big. | Shorten the input. |
| `throttled` | 429 | Too many requests for this route or user. | Wait `retry_after_seconds`, then retry; show the countdown. |
| `default_key_limit` | 429 | The daily limit on QueryLab's shared key is used up. `retry_after_seconds` is the time to midnight UTC. | Offer "add your own key" (`PUT /api/llm-keys/{provider}`); otherwise show when it resets. |
| `agent_run_limit` | 429 | Too many unfinished runs. Waiting does not help (`retry_after_seconds` is null). | Ask the user to approve, edit or cancel an open run (`GET /api/agent/limits` says how many). |
| `agent_stream_limit` | 429 | Too many live streams are open on the server. `retry_after_seconds` is null. | Fall back to polling `GET /api/agent/runs/{id}` every few seconds. |
| `internal_error` | 500 | Unexpected server error. | Show a generic failure; retry later. |
| `database_error` | 500 | A database error. | Retry later. |
| `configuration_error` | 500 | The server is misconfigured. | Tell the owner. |
| `encryption_not_configured` | 500 | No encryption key is set on the server. | Tell the owner. |
| `encryption_key_invalid` | 500 | The encryption key is invalid. | Tell the owner. |
| `not_implemented` | 501 | The feature does not exist yet. | Hide the feature. |
| `external_service_error` | 502 | An upstream service failed. | Retry later. |
| `service_unavailable` | 503 | The service is down for now. | Retry later. |
| `question_invalid` | 400 | The question is empty or too long. | Show the message; keep the text so it can be edited. |
| `guard_rejected` | 400 | The SQL was refused. On `/edit` the reason is in `errors[0].message` and the run stays paused. On `/result` and `/ask` the message is generic. | On edit: show the reason under the editor. Elsewhere: show the message. |
| `query_failed` | 422 | The query ran and the database refused it. | Show the message; for a run, open the trace. |
| `query_timeout` | 504 | The query took too long and was stopped. | Suggest a narrower question or a smaller date range. |
| `not_answerable` | 422 | The schema cannot answer this question (the message is the model's reason). | Show the reason; offer to rephrase. |
| `llm_error` | 502 | The AI request failed. | Retry; if it keeps failing, show the message. |
| `llm_invalid_key` | 400 / 502 | The provider rejected the key. | Ask for a new key. |
| `llm_rate_limited` | 502 | The provider is rate limiting the key. | Retry later. |
| `llm_insufficient_quota` | 502 | The key has no quota left. | Ask for another key. |
| `llm_timeout` | 502 | The provider timed out. | Retry. |
| `llm_unavailable` | 502 | The provider is down. | Retry later. |
| `llm_unsupported` | 502 | The provider cannot do what was asked. | Pick another model. |
| `llm_bad_response` | 502 | The provider answered with something unusable. | Retry. |
| `unknown_provider` | 400 | The provider in the URL is not supported. | A bug in the client. |
| `key_invalid` | 400 | The key looks invalid (length). | Ask for the key again. |
| `model_invalid` | 400 | The model is not available for that provider. | Pick from the list. |
| `run_not_found` | 404 | No such run (also another user's run). | Go back to history. |
| `run_not_awaiting_approval` | 409 | Approve, edit or cancel on a run that is not paused (a double click, or a run that moved on). | Reload the run and show its real state. |
| `run_not_succeeded` | 409 | `GET /result` on a run that has no result. | Show the run's status instead of a table. |
| `run_not_finished` | 409 | A thumbs up or down on a run that is still going. | Show the buttons only on finished runs. |
| `run_expired` | 409 | Nobody approved the SQL in time. | Show "expired"; offer to ask again. |
| `run_busy` | 409 | The run is being worked on right now. | Retry in a moment. |
| `table_not_found` | 404 | No such table in the schema. | Refresh the schema panel. |
| `workspace_not_found` | 404 | No such workspace (also another user's workspace: the answer is the same). | Go back to the workspace list. |
| `workspace_limit_reached` | 409 | The user already has the maximum number of workspaces (`meta.max_workspaces` on the list). | Offer to delete one. |
| `workspace_name_taken` | 409 | The user already has a workspace with this name. | Ask for another name. |
| `workspace_not_ready` | 409 | The workspace is still being created, or is being deleted. | Retry in a moment. |
| `demo_workspace_read_only` | 409 | Rename or delete on the shared demo workspace. | Hide those actions for the demo. |
| `workspace_gone` | 404 | A run's workspace was deleted: its trace can still be replayed, but its result can no longer be fetched. | Show the trace only. |
| `invalid_spec` | 422 | A table or column spec is unusable (no columns, the last column, a bad `on_delete`). | Show the message. |
| `table_name_taken` | 409 | The workspace already has a table with this name. | Ask for another name. |
| `column_name_taken` | 409 | The table already has a column with this name. | Ask for another name. |
| `table_limit_reached` | 409 | The workspace has the maximum number of tables. | Offer to drop one. |
| `column_limit_reached` | 409 | The table has the maximum number of columns. | Offer to drop one. |
| `relation_limit_reached` | 409 | The workspace has the maximum number of relations. | Offer to remove one. |
| `column_not_found` | 404 | No such column (the hidden `_row_id` cannot be addressed either). | Refresh the table. |
| `relation_not_found` | 404 | No such relation. | Refresh the relation list. |
| `relation_invalid` | 422 | The parent columns are not a primary key or unique, or the types differ. | Show the message; pick other columns. |
| `cast_failed` | 422 | A value cannot be converted to the new column type. `errors[0].message` names the first bad row id. Nothing changed. | Show the row; offer to fix the value or pick `text`. |
| `constraint_violation` | 409 | Existing rows break the key, relation or NOT NULL being added (or a row edit would break one). `errors[0].message` names the first row. Nothing changed. | Show the row; fix the data first. |
| `sql_invalid` | 400 | The SQL console refused the request before running it (empty, too long, too many statements, BEGIN/COMMIT/ROLLBACK, COPY). | Show the message. |
| `sql_failed` | 422 | A statement failed; the whole request was rolled back. `errors[0].message` is `Statement N: <SQLSTATE>: <message>`. | Show it under the editor. |
| `sql_busy` | 429 | Another SQL request of the user is still running. `retry_after_seconds` is null. | Wait for it, then run again. |
| `workspace_full` | 409 | The write would take the workspace over its size cap (and it was rolled back). | Offer to delete data or tables. |
| `user_storage_full` | 409 | The write would take the user's workspaces over their total size cap. | Offer to delete data or a workspace. |
| `row_not_found` | 404 | No row with this `_row_id` in the table (also another user's row: the workspace itself is a 404). | Refresh the rows. |
| `row_invalid` | 422 | A value does not fit its column. `errors[0].field` is `rows[i].column`. Nothing was written. | Mark the cell. |
| `too_many_rows` | 422 | More rows in one request than the per-request cap. | Send fewer rows. |
| `invalid_name` | 422 | A workspace, table or column name or a column type cannot be used. | Show the message next to the field. |
| `workspace_provisioning_failed` | 503 | The schema and roles could not be created; everything was cleaned up. | Retry later. |

## Run error codes (`error_code` on a failed or expired run, and on a step)

These are not HTTP errors: they sit in `RunOut.error_code` of a run with status `failed` or `expired`, and in a step's `error_code`.

| Code | Meaning | What the screen does |
|------|---------|----------------------|
| `not_answerable` | The agent decided the data cannot answer the question; the last step has its reason. | Show the reason. |
| `query_failed` | The approved SQL failed on the database and could not be repaired. | Show the last step; offer to edit the SQL. |
| `query_timeout` | The approved SQL took too long. | Suggest narrowing the question. |
| `guard_rejected` | The SQL was refused by the guard. | Show the reason from the trace. |
| `agent_steps_exceeded` | The run hit its step budget. | Offer to ask again, more specifically. |
| `agent_llm_calls_exceeded` | The run hit its LLM call budget. | Same. |
| `agent_tokens_exceeded` | The run hit its token budget. | Same. |
| `agent_revisions_exceeded` | The agent revised its SQL too many times. | Same. |
| `agent_timeout` | The run worked too long. | Same. |
| `agent_worker_lost` | The background worker stopped before the run finished. | Offer to ask again. |
| `workspace_gone` | The workspace the run asked about was deleted before the run could continue. | Show the trace; offer to ask again in another workspace. |
| `agent_internal_error` | An unexpected error inside the run. | Offer to ask again. |
| `llm_key_changed` | The user's key was removed or changed mid-run. | Ask again. |
| `run_expired` | Status `expired`: nobody approved in time. | Offer to ask again. |
| `tool_error` | On a step: a tool call failed and the model was told. Not a run failure by itself. | Show it in the trace. |
