# Step 2: Eval harness skeleton

**Goal:** one command scores a model on a question set by comparing what its SQL returns with what the correct SQL returns, and stores the result. We get baseline execution-accuracy numbers on two targets (Olist and Spider) and learn whether the step 1 confidence score tracks correctness. Backend only, runs on your machine, nothing new ships in the container except two small tables.

**Done when:**
- `python manage.py run_eval --target olist|spider --model <name>` runs a question set and prints a summary (accuracy, errors by reason, mean latency, tokens).
- Each run is stored as one `EvalRun` plus one `EvalResult` per question in the app database.
- Execution accuracy is computed by running the gold SQL and the model's SQL on the same database and comparing rows (rules in 2.4).
- The Olist target goes through the real `ask` pipeline (prompt, guard, reader role). The Spider target runs offline on SQLite.
- Spider dev is split once, by database, into `tune` and `held-out`; the split list is committed and the headline score is reported on `held-out` only.
- Baselines are recorded for Gemini 3.5 Flash on both targets (a second model, such as OpenAI, is optional: paid API keys are billed separately from chat plans), with accuracy per confidence bucket.
- The comparison logic is unit tested (including tricky cases), and the harness is tested end to end with the fake LLM.
- `backend/CLAUDE.md`, `FLOW.md` and `DECISION.md` are updated, and step 2 is ticked in the README.

**Scope:** the harness, the two question sets, the baseline run, and the confidence check. Not in scope: clustering or LLM-drafted expected SQL from real traces (step 6), the eval results API and regression gate (step 6), any screen (step 9), fine-tuning (step 7). Prompt tuning on `tune` is allowed but is not a goal of this step; we report what the step 1 prompt scores.

**What "correct" means.** We never store gold results. We store gold SQL and execute it at eval time on the same database as the model's SQL. A question is correct when both result sets match under the rules in 2.4. Known limit of execution accuracy: two different queries can return the same rows by chance. Spider's official scorer accepts this too.

**Container budget (1/4 vCPU, 1 GiB, image near its 300 MB limit):** the runtime image gains no dependencies. Spider needs only Python's built-in `sqlite3`. Any helper for downloading or unpacking goes in the `offline` group or uses the standard library. Evals are run from the host or CI, never in the container (see `DECISION.md`, "No heavy work in the container"). The two new tables are tiny.

**Trust model:** the Olist target reuses the step 1 layers (guard, reader role, caps). The gold SQL is trusted (written by us) but still runs on the reader role. Spider gold and model SQL run on a SQLite file opened read-only (`mode=ro`) with a time limit, because the Postgres guard does not apply there. Spider runs happen offline on your machine, never on a server.

**What goes to the LLM:** the same as step 1 (rules, schema, the question). No gold SQL and no gold rows are ever sent.

Each atomic task is one small commit with a Conventional Commit message (in practice the commits follow the numbered groups). **(You)** marks a task only you can do. Claude commits locally and never pushes.

---

## 2.1 Settings (strict, no fallbacks)

Every number and name goes into `.env` and `.env.example`, never into code (rule 0.2.6). The sync test keeps both in line.

- [x] **2.1.1** `EVAL_ROW_COMPARE_PRECISION` (decimal places when comparing numbers), `EVAL_MAX_COMPARE_ROWS` (rows read from each side), `EVAL_QUERY_TIMEOUT_MS` (per-query limit for gold and predicted SQL).
- [x] **2.1.2** `EVAL_OPENAI_API_KEY` (key used for the OpenAI baseline; the Gemini baseline reuses `LLM_DEFAULT_GEMINI_API_KEY`). `.env` only, never in the database or logs.
- [x] **2.1.3** `EVAL_SPIDER_DIR` (where Spider is unpacked, under `infra/data/spider/`). The split is a committed file, not a setting (see 2.5.4).
- [x] **2.1.4** `EVAL_CONFIDENCE_BUCKETS` (comma list of edges, for example `0.5,0.7,0.85`), plus `EVAL_LLM_RETRIES`, `EVAL_CONFIRM_ABOVE_CALLS` (cost guard, 2.7.5) and `EVAL_MODEL_PRICES` (cost estimate, 2.8.1).
- [x] **2.1.5** Read each with `django-environ` and no default; add to `.env.example` and the test env; the sync test passes.

## 2.2 Models and migration

- [x] **2.2.1** Create a new Django app `evals` (layout: `models.py`, `compare.py`, `runner.py`, `scoring.py`, `targets/`, `management/commands/`, `tests/`). Register it in `INSTALLED_APPS`.
- [x] **2.2.2** `EvalRun`: target (`olist` or `spider`), split (`all`, `tune`, `held-out`), provider, model, prompt version, question count, correct count, started, finished, status. No user foreign key (runs are made by the owner on the command line).
- [x] **2.2.3** `EvalResult`: run, question id, question, gold SQL, predicted SQL, outcome (`correct`, `wrong`, `error`, `timeout`, `guard_rejected`, `not_answerable`, `llm_failed`), reason (short), confidence, attempts, input and output tokens, latency.
- [x] **2.2.4** Migration on the `default` database only (the router already guarantees this). Gold and predicted result rows are never stored.
- [x] **2.2.5** Tests: models create and relate, and no field can hold result rows.

## 2.3 Make the pipeline reusable

The step 1 `answer(user, question)` mixes key lookup, daily limits and `AskLog` writing with the core path. The harness needs the core without a user.

- [x] **2.3.1** Extract the pure core from `ask/service.py` as `generate_and_run(provider, question, schema_text, dialect, run_sql, guard)` (build the prompt, call the LLM, parse, guard, run, repair loop). `answer()` calls it and keeps the key, limit and log handling around it. Behaviour of `POST /api/ask` must not change.
- [x] **2.3.2** Give the prompt builder a dialect parameter (`postgres` default, `sqlite`). The system prompt names the dialect and the fully qualified `demo.` rule applies to Postgres only.
- [x] **2.3.3** Prompt version string constant stored on each `EvalRun`, so scores can be tied to the prompt that produced them.
- [x] **2.3.4** Tests: the whole existing step 1 suite still passes unchanged, plus new tests for the extracted core and for the SQLite prompt.

## 2.4 Result comparison (the heart of the harness)

`compare.py` takes two result sets and returns a verdict and a short reason. Pure functions, no database.

- [x] **2.4.1** Normalise values: numbers rounded to `EVAL_ROW_COMPARE_PRECISION` (so `12`, `12.0` and `Decimal('12.00')` match), booleans kept apart from numbers, dates and times as ISO strings, text trimmed, `NULL` as `None`.
- [x] **2.4.2** Ignore column names. Compare by column position first; if the column count matches but the order differs, try to match columns by their values and accept a consistent permutation.
- [x] **2.4.3** Rows compared as an unordered multiset. If the gold SQL has a top-level `ORDER BY` (detected with sqlglot), compare in order instead.
- [x] **2.4.4** Ties under `LIMIT` are not handled by the comparison (it cannot know the ordering key). The Olist gold SQL uses deterministic tie-breaks; for Spider, a tie at the cut is accepted noise, as in its official scorer. Documented in `DECISION.md` (2.10.3).
- [x] **2.4.5** Verdicts and reasons: `match`, `different_row_count`, `different_values`, `different_columns`. Never log or store the rows themselves.
- [x] **2.4.6** Table-driven tests (about 30 cases): equal results, reordered rows, reordered columns, aliases, `12` vs `12.0`, `None` vs empty, duplicates, ordered vs unordered gold, ties, empty vs empty, one extra row.

## 2.5 Spider target (offline, SQLite)

- [ ] **2.5.1** (You) Download Spider and unpack it into `infra/data/spider/` (CC BY-SA 4.0; never committed). `make eval ARGS=check_spider` prints the exact steps and checks the layout and the split.
- [x] **2.5.2** Check `.gitignore` and `.dockerignore` cover `infra/data/spider/`, so the data never enters git or the image.
- [x] **2.5.3** Spider loader: read `dev.json` and `tables.json`; yield `(db_id, question, gold_sql)`. Skip the known malformed examples; list the skipped ids in the output.
- [x] **2.5.4** Split: assign each of the 20 dev databases to `tune` or `held-out` once (stratified by size), write the lists to `evals/targets/spider_split.json`, commit it. A test fails if a database is in both or neither.
- [x] **2.5.5** SQLite schema renderer: `CREATE TABLE` text from `PRAGMA table_info` / `foreign_key_list`, with a few sample values per low-cardinality text column (same limits as the Postgres side).
- [x] **2.5.6** SQLite executor: open the file with `mode=ro`, set a time limit through the progress handler, cap rows at `EVAL_MAX_COMPARE_ROWS`. The Postgres guard is not used here; the read-only open mode is the wall.
- [x] **2.5.7** Tests on a tiny fixture SQLite database: schema rendering, execution, row cap, timeout, and a write attempt that must fail.

## 2.6 Olist target (real pipeline)

- [x] **2.6.1** Write the golden set: about 40 questions in `evals/targets/olist_golden.jsonl` (`id`, `question`, `gold_sql`, `tags`). Mix: counts, joins across 3 or more tables, date logic, top-N with deterministic tie-breaks, category-name translation, and 4 unanswerable questions (expected outcome `not_answerable`).
- [ ] **2.6.2** (You) Review each gold query: run it, look at the rows, confirm it answers the question. `make eval ARGS=review_golden` prints each query with its rows; when you are satisfied, `make eval ARGS="review_golden --mark-reviewed"`. Unreviewed questions are skipped by `run_eval`.
- [x] **2.6.3** Olist executor: gold SQL runs through the same `runner` and the reader connection. Predicted SQL goes through the full pipeline (guard included).
- [x] **2.6.4** Handle unanswerable questions: correct when the model declines (`not_answerable`), wrong when it returns SQL.
- [x] **2.6.5** Tests with the fake LLM returning gold SQL (all correct), wrong SQL (all wrong), hostile SQL (guard rejected), and a decline.

## 2.7 Runner and command

- [x] **2.7.1** `run_eval` builds a provider for a model from `.env` keys (no user, no `UserLLMKey`), and refuses a model not listed in `LLM_*_MODELS`.
- [x] **2.7.2** Loop over the questions: one at a time, no threads (rule: 1/4 vCPU). On a provider rate limit, back off and retry a bounded number of times, then record `llm_failed`.
- [x] **2.7.3** Options: `--target`, `--split`, `--model`, `--limit N` (sample), `--seed`, `--resume <run id>` so a crashed run does not start over.
- [x] **2.7.4** Write each `EvalResult` as it completes (so progress survives a crash), then close the run with totals.
- [x] **2.7.5** Cost guard: print the planned number of LLM calls before starting and require `--yes` above a threshold.
- [x] **2.7.6** Tests: a full run with the fake LLM on a small fixture set, resume after an interrupted run, and the cost guard.

## 2.8 Scoring and confidence check

- [x] **2.8.1** `scoring.summarise(run)`: execution accuracy, outcome counts, accuracy by tag, mean and p95 latency, tokens, and a rough cost estimate from a price table in `DECISION.md` terms (prices in settings, not code).
- [x] **2.8.2** Confidence calibration: accuracy per bucket from `EVAL_CONFIDENCE_BUCKETS`, with counts, and a simple rank correlation between confidence and correctness.
- [x] **2.8.3** `eval_report --run <id>` prints both as plain text; `--compare <id> <id>` shows two runs side by side.
- [x] **2.8.4** Tests on a hand-built run: known accuracy, known buckets.

## 2.9 Baselines

- [ ] **2.9.1** (You, optional) Choose a second model: the OpenAI model for the baseline (default proposal: `gpt-5-mini`) and set `EVAL_OPENAI_API_KEY` in `backend/.env`. Confirm the API budget; a full Spider dev run is about 1,000 calls per model.
- [ ] **2.9.2** Smoke run: 10 Olist questions on Gemini 3.5 Flash. Read the failures with you before spending on the full run.
- [ ] **2.9.3** (You, with Claude reading the output) Full Olist golden set on both models.
- [ ] **2.9.4** (You) Spider `held-out` on both models; Spider `tune` on one model to see the gap.
- [ ] **2.9.5** Record the numbers in `backend/DECISION.md`: model, split, prompt version, accuracy, notable error patterns, and whether the confidence score separates right from wrong. If it does not, list what to change (decided in a later step, not fixed here).

## 2.10 Project documents

- [x] **2.10.1** `backend/CLAUDE.md`: the `evals` app layout, the rule "eval runs happen on the host, never in the container", the new `.env` keys, and the rule that gold SQL never reaches a prompt.
- [x] **2.10.2** `backend/FLOW.md`: the eval flow (question set to model to execute both SQLs to compare to store to report) for each target.
- [x] **2.10.3** `backend/DECISION.md`: execution accuracy and its limits, the Spider split by database, comparing by multiset, Olist goes through the real pipeline and Spider does not, no heavy dependencies, the baseline numbers (from 2.9.5).
- [x] **2.10.4** `frontend/` docs get one line noting step 6 will expose eval results to the dashboard (no code).
- [x] **2.10.5** Tick step 2 in the root README and update its status line.

---

## Decisions

- Gold results are never stored; gold SQL is executed alongside the prediction on the same data.
- Execution accuracy compares rows as an unordered multiset (ordered when the gold SQL orders), ignoring column names and rounding numbers.
- Spider is split once by database, committed, and the headline number is reported on `held-out` only.
- Olist uses the real pipeline (guard and reader role); Spider uses a read-only SQLite file.
- Evals run in the dev container (`make eval`), never in the production container, one question at a time; the container image gains no dependencies.
- `answer()` is split so the harness can reuse the core without a user, keys or `AskLog`.
- Open items for the owner: OpenAI baseline model and budget (2.9.1), and whether to generate `backend/.env.test` from `.env.example` (open since step 1).
