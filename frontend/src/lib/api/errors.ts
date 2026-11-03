/*
 * What each API error code means for the user. Generated from backend/API_ERRORS.md
 * (the source of truth); errors.test.ts fails when the two drift. Screens branch on
 * `code`, never on the message. No entry here ever tells the user to wait for an
 * automatic retry, because this app does not retry (DECISION.md).
 */

export type ErrorInfo = { message: string; hint: string }

export const ERROR_INFO: Record<string, ErrorInfo> = {
  authentication_denied: {
    message: 'Not signed in (or the session ended).',
    hint: 'Go to sign-in.',
  },
  invalid_token: {
    message: 'A token was invalid (not used by the browser flow).',
    hint: 'Go to sign-in.',
  },
  token_expired: {
    message: 'A token expired (not used by the browser flow).',
    hint: 'Go to sign-in.',
  },
  permission_denied: {
    message: 'Signed in but not allowed (also a failed CSRF check).',
    hint: 'Reload the page, then try again.',
  },
  staff_only: {
    message: 'The workbench (/api/workbench/...) is for staff accounts only.',
    hint: 'Hide the workbench; show "not available".',
  },
  case_not_found: {
    message: 'No such trace case.',
    hint: 'Reload the case list.',
  },
  case_not_reviewable: {
    message: 'The case is not drafted (already approved, rejected or not drafted yet).',
    hint: 'Reload the case.',
  },
  draft_unusable: {
    message: 'The draft failed its checks and no corrected SQL was sent.',
    hint: 'Ask the reviewer to edit the SQL.',
  },
  eval_run_not_found: {
    message: 'No such eval run.',
    hint: 'Reload the run list.',
  },
  eval_runs_not_comparable: {
    message: 'The two runs scored different targets.',
    hint: 'Pick two runs of the same target.',
  },
  not_found: {
    message: 'No such route or resource.',
    hint: 'Show "not found".',
  },
  method_not_allowed: {
    message: 'Wrong HTTP method for the route.',
    hint: 'A bug in the client.',
  },
  unsupported_media_type: {
    message: 'Body was not JSON.',
    hint: 'A bug in the client.',
  },
  bad_request: {
    message: 'The request was malformed.',
    hint: 'Show the message.',
  },
  validation_error: {
    message: 'A field is missing or invalid; errors names the fields.',
    hint: 'Show each errors[].message next to its field.',
  },
  unprocessable_entity: {
    message: 'Well formed but not acceptable.',
    hint: 'Show the message.',
  },
  conflict: {
    message: 'Generic state conflict.',
    hint: 'Reload the resource.',
  },
  duplicate_resource: {
    message: 'The resource already exists.',
    hint: 'Show the message.',
  },
  stale_data: {
    message: 'The resource changed since it was read.',
    hint: 'Reload, then try again.',
  },
  resource_locked: {
    message: 'The resource is locked.',
    hint: 'Retry later.',
  },
  payload_too_large: {
    message: 'Body too big.',
    hint: 'Shorten the input.',
  },
  throttled: {
    message: 'Too many requests for this route or user.',
    hint: 'Wait a moment, then try again.',
  },
  default_key_limit: {
    message:
      "The daily limit on QueryLab's shared key is used up. retry_after_seconds is the time to midnight UTC.",
    hint: 'Offer "add your own key" (PUT /api/llm-keys/{provider}); otherwise show when it resets.',
  },
  agent_run_limit: {
    message: 'Too many unfinished runs. Waiting does not help (retry_after_seconds is null).',
    hint: 'Ask the user to approve, edit or cancel an open run (GET /api/agent/limits says how many).',
  },
  agent_stream_limit: {
    message: 'Too many live streams are open on the server. retry_after_seconds is null.',
    hint: 'Reload the page to try again.',
  },
  internal_error: {
    message: 'Unexpected server error.',
    hint: 'Show a generic failure; retry later.',
  },
  database_error: {
    message: 'A database error.',
    hint: 'Retry later.',
  },
  configuration_error: {
    message: 'The server is misconfigured.',
    hint: 'Tell the owner.',
  },
  encryption_not_configured: {
    message: 'No encryption key is set on the server.',
    hint: 'Tell the owner.',
  },
  encryption_key_invalid: {
    message: 'The encryption key is invalid.',
    hint: 'Tell the owner.',
  },
  not_implemented: {
    message: 'The feature does not exist yet.',
    hint: 'Hide the feature.',
  },
  external_service_error: {
    message: 'An upstream service failed.',
    hint: 'Retry later.',
  },
  service_unavailable: {
    message: 'The service is down for now.',
    hint: 'Retry later.',
  },
  question_invalid: {
    message: 'The question is empty or too long.',
    hint: 'Show the message; keep the text so it can be edited.',
  },
  guard_rejected: {
    message:
      'The SQL was refused. On /edit the reason is in errors[0].message and the run stays paused. On /result and /ask the message is generic.',
    hint: 'On edit: show the reason under the editor. Elsewhere: show the message.',
  },
  query_failed: {
    message: 'The query ran and the database refused it.',
    hint: 'Show the message; for a run, open the trace.',
  },
  query_timeout: {
    message: 'The query took too long and was stopped.',
    hint: 'Suggest a narrower question or a smaller date range.',
  },
  not_answerable: {
    message: "The schema cannot answer this question (the message is the model's reason).",
    hint: 'Show the reason; offer to rephrase.',
  },
  llm_error: {
    message: 'The AI request failed.',
    hint: 'Retry; if it keeps failing, show the message.',
  },
  llm_invalid_key: {
    message: 'The provider rejected the key.',
    hint: 'Ask for a new key.',
  },
  llm_rate_limited: {
    message: 'The provider is rate limiting the key.',
    hint: 'Retry later.',
  },
  llm_insufficient_quota: {
    message: 'The key has no quota left.',
    hint: 'Ask for another key.',
  },
  llm_timeout: {
    message: 'The provider timed out.',
    hint: 'Retry.',
  },
  llm_unavailable: {
    message: 'The provider is down.',
    hint: 'Retry later.',
  },
  llm_unsupported: {
    message: 'The provider cannot do what was asked.',
    hint: 'Pick another model.',
  },
  llm_bad_response: {
    message: 'The provider answered with something unusable.',
    hint: 'Retry.',
  },
  unknown_provider: {
    message: 'The provider in the URL is not supported.',
    hint: 'A bug in the client.',
  },
  key_invalid: {
    message: 'The key looks invalid (length).',
    hint: 'Ask for the key again.',
  },
  model_invalid: {
    message: 'The model is not available for that provider.',
    hint: 'Pick from the list.',
  },
  no_key_for_provider: {
    message: 'There is no saved key for that provider.',
    hint: 'Save a key for it first.',
  },
  no_active_key: {
    message: 'You chose your own AI but no key is in use.',
    hint: 'Add a key and mark it as in use, or switch back to QueryLab AI.',
  },
  unknown_ai_source: {
    message: 'That AI choice is not supported.',
    hint: 'Reload the page and try again.',
  },
  run_not_found: {
    message: "No such run (also another user's run).",
    hint: 'Go back to history.',
  },
  run_not_awaiting_approval: {
    message: 'Approve, edit or cancel on a run that is not paused (a double click, or a run that moved on).',
    hint: 'Reload the run and show its real state.',
  },
  run_not_succeeded: {
    message: 'GET /result on a run that has no result.',
    hint: "Show the run's status instead of a table.",
  },
  run_not_finished: {
    message: 'A thumbs up or down on a run that is still going.',
    hint: 'Show the buttons only on finished runs.',
  },
  run_expired: {
    message: 'Nobody approved the SQL in time.',
    hint: 'Show "expired"; offer to ask again.',
  },
  run_busy: {
    message: 'The run is being worked on right now.',
    hint: 'Retry in a moment.',
  },
  table_not_found: {
    message: 'No such table in the schema.',
    hint: 'Refresh the schema panel.',
  },
  workspace_not_found: {
    message: "No such workspace (also another user's workspace: the answer is the same).",
    hint: 'Go back to the workspace list.',
  },
  workspace_limit_reached: {
    message: 'The user already has the maximum number of workspaces (meta.max_workspaces on the list).',
    hint: 'Offer to delete one.',
  },
  workspace_name_taken: {
    message: 'The user already has a workspace with this name.',
    hint: 'Ask for another name.',
  },
  workspace_not_ready: {
    message: 'The workspace is still being created, or is being deleted.',
    hint: 'Retry in a moment.',
  },
  demo_workspace_read_only: {
    message: 'Rename or delete on the shared demo workspace.',
    hint: 'Hide those actions for the demo.',
  },
  workspace_gone: {
    message:
      "A run's workspace was deleted: its trace can still be replayed, but its result can no longer be fetched.",
    hint: 'Show the trace only.',
  },
  sql_invalid: {
    message:
      "This query runner only reads (SELECT, WITH, EXPLAIN, SHOW), and the SQL can't be empty or too long.",
    hint: 'Change the SQL and run it again. To change data, import a dump.',
  },
  sql_failed: {
    message:
      'A statement failed; the whole request was rolled back. errors[0].message is Statement N: <SQLSTATE>: <message>.',
    hint: 'Show it under the editor.',
  },
  sql_busy: {
    message: 'Another SQL request of the user is still running. retry_after_seconds is null.',
    hint: 'Wait for it, then run again.',
  },
  workspace_full: {
    message: 'The dump would take the workspace over its size limit, so nothing was imported.',
    hint: 'Use a smaller dump or delete the workspace data first.',
  },
  user_storage_full: {
    message: 'The dump would take your workspaces over their total size limit.',
    hint: 'Delete a workspace you no longer need, or use a smaller dump.',
  },
  invalid_name: {
    message: "That name can't be used, or the file is empty or not a .sql or .sql.gz file.",
    hint: 'Check the name or choose a pg_dump file.',
  },
  dump_too_large: {
    message: 'The dump is too large.',
    hint: 'Make a smaller dump, for example one schema or fewer tables.',
  },
  dump_upload_missing: {
    message: 'The uploaded file was not found.',
    hint: 'Upload the file again.',
  },
  import_in_progress: {
    message: 'You already have an import running.',
    hint: 'Wait for it to finish, then try again.',
  },
  import_not_found: {
    message: 'No such import in this workspace.',
    hint: 'Go back to the workspace.',
  },
  import_not_ready: {
    message: 'This import is not waiting for an upload.',
    hint: 'Check its status.',
  },
  workspace_not_empty: {
    message: 'This workspace already has tables.',
    hint: "Tick 'Replace the tables already here' and import again.",
  },
  dump_refused: {
    message: 'The dump ends in the middle of a statement.',
    hint: 'Make the dump again and upload the whole file.',
  },
  dump_failed: {
    message: 'Postgres refused a statement in the dump.',
    hint: 'Fix that statement and upload again.',
  },
  dump_timeout: {
    message: 'The import took too long and was stopped.',
    hint: 'Use a smaller dump.',
  },
  dump_encoding: {
    message: 'The dump must be UTF-8 text.',
    hint: 'Dump again with UTF-8 encoding.',
  },
  dump_interrupted: {
    message: 'The import was interrupted.',
    hint: 'Upload the dump again.',
  },
  dump_replaced: {
    message: 'An upload that never finished was replaced by your next import.',
    hint: 'Nothing to do.',
  },
  workspace_provisioning_failed: {
    message: 'The schema and roles could not be created; everything was cleaned up.',
    hint: 'Retry later.',
  },
  agent_steps_exceeded: {
    message: 'The run hit its step budget.',
    hint: 'Offer to ask again, more specifically.',
  },
  agent_llm_calls_exceeded: {
    message: 'The run hit its LLM call budget.',
    hint: 'Same.',
  },
  agent_tokens_exceeded: {
    message: 'The run hit its token budget.',
    hint: 'Same.',
  },
  agent_revisions_exceeded: {
    message: 'The agent revised its SQL too many times.',
    hint: 'Same.',
  },
  agent_timeout: {
    message: 'The run worked too long.',
    hint: 'Same.',
  },
  agent_worker_lost: {
    message: 'The background worker stopped before the run finished.',
    hint: 'Offer to ask again.',
  },
  agent_internal_error: {
    message: 'An unexpected error inside the run.',
    hint: 'Offer to ask again.',
  },
  llm_key_changed: {
    message: "The user's key was removed or changed mid-run.",
    hint: 'Ask again.',
  },
  tool_error: {
    message: 'On a step: a tool call failed and the model was told. Not a run failure by itself.',
    hint: 'Show it in the trace.',
  },
}

/** The user-facing text for a code; unknown codes fall back to the server's own message. */
export function describeError(code: string, serverMessage: string): ErrorInfo {
  return ERROR_INFO[code] ?? { message: serverMessage, hint: '' }
}
