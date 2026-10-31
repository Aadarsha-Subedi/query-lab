# Step 6: Trace-driven evals

**Goal:** turn the agent's stored traces into a living eval set, and make a prompt or model change prove itself against it. The owner picks interesting traces, an LLM drafts the expected SQL, the owner reviews it by hand, and approved cases join the eval set. Results are readable per failure cluster, and a regression gate says whether a change made things worse. Backend only; tested through Postman. The workbench screens are step 9.

**Done when:**
- Staff-only trace endpoints list and filter `AgentRun` traces and show one in full. Runs on user workspaces (`excluded_from_evals`) never appear.
- A user can mark their own run 👍 or 👎 (one vote per run, changeable).
- `build_candidates` picks the runs worth reviewing by fixed rules, and `cluster_candidates` groups them (layer 1 exact keys, layer 2 question similarity) with a label, size and representative.
- For a cluster representative, an LLM drafts expected SQL. The draft must pass the guard and run on the reader before a person sees it.
- The owner approves, edits or rejects each draft through the API. Only approved cases enter the trace eval set; the draft is never used as gold.
- `run_eval --target traces` scores a model on the approved cases with the step 2 comparison, for the `ask` and `agent` runners.
- Read-only eval API: runs, per-case results, per-cluster accuracy, and a comparison of two runs (which cases flipped).
- `run_eval --gate` compares a run to a stored baseline and exits non-zero when accuracy drops by more than the `.env` threshold, listing the flipped cases.
- The step 3 confidence follow-up is answered with reviewed labels and recorded in `DECISION.md`.
- No new dependency; the image stays at or under 300 MB (295 today).
- `backend/CLAUDE.md`, `FLOW.md`, `DECISION.md` are updated and step 6 is ticked in the root README.

**Decisions already made (owner, 2026-10-31):** step 6 is backend only; runs on user workspaces are excluded; human review of every expected SQL; evals run offline in the dev container, never in the production container; ML dependencies stay offline.

**Recommended answers to the thread's four questions (assumed below, change before 6.1 if you disagree):** the workbench is staff-only; clustering is deterministic, no ML libraries; a 👍/👎 signal is added; the gate threshold is an `.env` value with no default.

**Out of scope:** any screen (step 9), editing the Olist golden set from here (it keeps its own review flow), embedding-based clustering (a later offline upgrade), training data export (step 7), running evals inside the production container, a public eval dashboard (step 10).

**Open questions for the owner** (recommendation first; the plan assumes the first answer):
1. *Who may use the workbench:* `is_staff` users only. The platform has no roles beyond that, and the traces hold other people's questions. Alternative: any signed-in user sees only their own runs, which defeats the purpose.
2. *Question text in the eval set:* user questions are free text and may hold personal data. Recommendation: an approved case stores the question as the reviewer saw it, and the reviewer may edit it (6.4.4) to remove anything personal before approving. Alternative: store only reviewer-written paraphrases, which costs more review time.
3. *Retention of traces:* none is defined yet (DECISION.md, step 1). Recommendation: decide before real users arrive; this step only reads traces and adds no deletion.

**Container budget (1/4 vCPU, 1 GiB, image 295 of 300 MB):** stdlib plus sqlglot (already installed) and the existing Huey, Redis and LLM client. Candidate building and clustering stream rows in batches, not the whole table in memory. Drafting is a Huey job, one LLM call per cluster representative, never one per run. Running an eval stays a dev-container command. The image-size check runs first (6.1.1) and last (6.9.5).

**Trust model:**
- Staff checks are enforced in one dependency, applied to every workbench route, and a test lists all routes and fails when one lacks it.
- Drafted SQL is untrusted model output: it passes `guard.check` and runs on the reader connection (statement timeout, row cap) before a reviewer sees it, and the same again when an eval scores it. The reviewer's edit is guarded too.
- The prompt for drafting gets the question, the schema text and, when present, the SQL the user approved or edited. It never gets result rows.
- A case is never trusted until `status=approved`; the drafting model and the model being evaluated are not required to differ, but the case records which model drafted it.
- Trace endpoints never return another table's data: they read `AgentRun`/`AgentStep` and the new tables only.

Each atomic task is one small commit (Conventional Commits). **(You)** marks a task only you can do. Claude commits locally and never pushes.

---

## 6.1 Preparation

- [ ] **6.1.1** Run the image-size check on the branch and record the number in `DECISION.md`. If headroom is under 3 MB, stop and trim first.
- [ ] **6.1.2** Branch `feat/step-6-trace-evals` from `feat/step-5-workspaces` (or from `main` once step 5 is merged).
- [ ] **6.1.3** Read how `evals.runner`, `evals.agent_runner`, `Target`, `compare` and `scoring` fit together, and how `OlistTarget` loads questions. Write a short table in `FLOW.md` of what a new `traces` target must provide.
- [ ] **6.1.4** Settings, in `.env.example`, `.env`, `.env.test` and settings with no defaults, plus the `.env` sync test: `TRACES_CANDIDATE_MAX_AGE_DAYS`, `TRACES_CLUSTER_SIMILARITY`, `TRACES_CLUSTER_MAX_RUNS`, `TRACES_DRAFT_MODEL`, `TRACES_DRAFT_MAX_PER_BATCH`, `TRACES_PAGE_SIZE_MAX`, `EVAL_GATE_MAX_DROP_POINTS`, `EVAL_GATE_MIN_CASES`.

## 6.2 Trace API (staff only)

- [ ] **6.2.1** `IsStaff` dependency in `common`, a typed `403 staff_only` in `API_ERRORS.md`, and the route-list test (every route under `/api/workbench/` has it).
- [ ] **6.2.2** `GET /api/workbench/runs`: all demo-workspace runs with `excluded_from_evals=False`, filters for status, error code, edited, revisions, check label, feedback, date range, text search, ordering through the `common/order` allowlist, standard pagination. One query per page (annotations, no per-row lookups).
- [ ] **6.2.3** `GET /api/workbench/runs/{id}`: the run, all its steps (plan, tools, approval, execute preview, reflect), the SQL the agent proposed first and the SQL finally approved, and a `diff` flag when the user edited it. Result rows stay out; the stored preview is shown as is.
- [ ] **6.2.4** Tests: a staff user sees demo runs only; a workspace run is never returned or fetched (404); a non-staff user gets 403 on every route.

## 6.3 Feedback signal

- [ ] **6.3.1** Model `RunFeedback` (run, user, vote `up | down`, optional short note, timestamps), unique `(run, user)`, in `agent`; migration.
- [ ] **6.3.2** `PUT /api/agent/runs/{id}/feedback` and `DELETE` for the run's owner only, on a terminal run, throttled like the other run writes. `feedback` (your vote or null) added to the run schema; OpenAPI regenerated with `make openapi`.
- [ ] **6.3.3** Tests: only the owner votes; a vote changes rather than duplicates; a running run is refused; the error codes are in `API_ERRORS.md` (drift test).

## 6.4 Candidates and expected SQL (hand-reviewed)

- [ ] **6.4.1** Model `TraceCase` in `evals`: source run (plain nullable id, so a run can disappear later without losing the case), question, `draft_sql`, `draft_model`, `draft_error`, `gold_sql` (set only on approval), `status` (`candidate | drafted | approved | rejected`), `cluster_key`, `reviewer`, `reviewed_at`, `answerable`, `note`; unique on the source run; migration.
- [ ] **6.4.2** `evals/candidates.py` `build_candidates()`: rules that pick runs, each with a recorded reason: user edited the SQL, 👎, failed (any error code), revisions at least 1, `not_answerable`, check label `needs_look`. Skips `excluded_from_evals`, runs older than `TRACES_CANDIDATE_MAX_AGE_DAYS`, and runs already a case. Idempotent. Management command `build_trace_cases`.
- [ ] **6.4.3** Drafting job (Huey): `draft_expected_sql(case)` builds the prompt (question, schema text, and the user's approved SQL when the run was edited), calls `TRACES_DRAFT_MODEL`, parses, runs `guard.check` and executes on the reader. A failure is stored in `draft_error`, not raised. One call per cluster representative; `TRACES_DRAFT_MAX_PER_BATCH` caps a batch; uses the default key budget accounting like every other LLM call.
- [ ] **6.4.4** Review endpoints (staff): `GET /api/workbench/cases` (filter by status and cluster, shows the draft, its rows preview and the trace link), `POST /cases/{id}/approve` (optionally with edited `question` and `sql`; the SQL is guarded and executed again before it is saved as `gold_sql`), `POST /cases/{id}/reject` (with a reason), `POST /cases/{id}/mark-unanswerable`. Only `drafted` cases can be approved.
- [ ] **6.4.5** Tests: rules pick exactly the intended runs; a workspace run is never a case; a draft that fails the guard is stored with its error and cannot be approved unedited; an edited approval is guarded; approving twice is refused; no result rows are stored on a case.

## 6.5 Clustering

- [ ] **6.5.1** `evals/clustering.py` feature extraction with sqlglot: outcome class, set of tables, and a shape fingerprint (literals replaced by placeholders; join count, aggregate functions, GROUP BY, window, subquery or CTE, ORDER BY with LIMIT). Pure functions; unit tests with literal-only differences giving the same fingerprint.
- [ ] **6.5.2** Layer 1: group by `(outcome, tables, fingerprint)`; the key is stored as `TraceCase.cluster_key`.
- [ ] **6.5.3** Layer 2: within the same outcome and tables, merge groups whose questions overlap (lowercase, stopwords removed, Jaccard on word sets at `TRACES_CLUSTER_SIMILARITY`, single link). Deterministic: ties broken by run id, so the same traces always give the same clusters. A cap on runs per pass (`TRACES_CLUSTER_MAX_RUNS`) keeps memory bounded.
- [ ] **6.5.4** Cluster summary: a rule-built label (outcome, tables, shape in words), size, representative (most signals, then newest) and member ids. `GET /api/workbench/clusters` returns them largest first, with counts of cases per status.
- [ ] **6.5.5** Tests: same pattern phrased differently merges; different tables never merge; reruns give identical clusters; an empty set and a single run work; 1,000 synthetic runs cluster inside a time bound on the dev container.

## 6.6 Eval on trace cases

- [ ] **6.6.1** `evals/targets/traces.py`: a `Target` that serves approved `TraceCase` rows as `EvalQuestion`s (`tags` hold the cluster key), with the demo schema, guard and reader exactly like `OlistTarget`. `--target traces` in `run_eval` for both runners.
- [ ] **6.6.2** `EvalResult` keeps its shape; store the `cluster_key` and `trace_case` id on the result (migration) so results group by cluster without joins on tags.
- [ ] **6.6.3** The gold for an unanswerable case means "decline", handled as `OlistTarget` does.
- [ ] **6.6.4** Tests: only approved cases are served; a rejected or drafted case never is; a run records its cluster per result; the run works with the fake LLM used in the step 2 tests.

## 6.7 Eval results API (read only)

- [ ] **6.7.1** `GET /api/workbench/eval/runs` (filter by target, runner, model, prompt version) with accuracy, cost per question, finished time.
- [ ] **6.7.2** `GET /api/workbench/eval/runs/{id}` with per-case results (question, gold, predicted, outcome, reason, link to the source trace) and `by_cluster` accuracy.
- [ ] **6.7.3** `GET /api/workbench/eval/compare?base={id}&other={id}`: the shared cases, which flipped to wrong or to correct, accuracy difference, per-cluster difference. Built on `evals/compare.py`.
- [ ] **6.7.4** Tests: staff only; comparing runs from different targets is refused with a typed error; the numbers match the step 2 report command on the same data.

## 6.8 Regression gate

- [ ] **6.8.1** `evals/gate.py`: given a candidate run and a baseline run, fail when accuracy drops by more than `EVAL_GATE_MAX_DROP_POINTS`, or when fewer than `EVAL_GATE_MIN_CASES` cases are shared (too small to trust). It also reports flipped cases and per-cluster drops. Pure logic with tests.
- [ ] **6.8.2** `run_eval --gate --baseline {id}` (and `--gate` alone, which uses the latest done run of the same target, split, runner and prompt version): prints the verdict, exits 0 or 1.
- [ ] **6.8.3** `make eval-gate` documented in `FLOW.md`: it runs the Olist golden set and the trace set, because the live key is only in the dev environment. CI runs the gate logic with a fake LLM, not a live model.
- [ ] **6.8.4** Tests: a drop at the threshold passes and one point beyond fails; a flip in both directions is listed; too few cases fail clearly; exit codes.

## 6.9 Confidence follow-up and close-out

- [ ] **6.9.1** Extend `confidence_analysis` to accept reviewed trace cases as labels and report check-label vs correctness, the features that varied, and rank correlation. No new score is shipped in this step.
- [ ] **6.9.2** **(You)** Review the first batch of drafted cases in Postman (`FLOW.md` has the exact requests) and run the Olist agent eval from step 3 so the confidence report has real data. Needs the live Gemini key.
- [ ] **6.9.3** Record the confidence verdict, the clustering settings chosen and the first trace-set baseline in `DECISION.md`.
- [ ] **6.9.4** `backend/openapi.json` regenerated; `API_ERRORS.md` drift test and route-list test pass; `ruff`, `mypy` and the full test suite pass.
- [ ] **6.9.5** Final image-size check with CI's method; record it in `DECISION.md`.
- [ ] **6.9.6** Update `backend/CLAUDE.md`, `FLOW.md` ("The workbench contract" for step 9) and `DECISION.md`; tick step 6 in the root README, note what remains for you.
