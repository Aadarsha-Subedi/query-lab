# Step 7: LoRA fine-tune (time-boxed stretch)

**Goal:** fine-tune a small open model on text-to-SQL with LoRA, then prove with the existing eval harness whether it beats its own base model. The result is reported honestly in `DECISION.md`, whichever way it goes. Backend only; nothing in this step runs in the production container.

**Done when:**
- A dataset builder writes instruction JSONL (train and validation) in the product's own prompt format, from Spider `train` plus the Spider `tune` half, with an optional reviewed-trace-case source. Held-out Spider databases and the Olist golden set never appear in it, and a test proves it.
- A Colab notebook (committed as a plain `.py`-style `.ipynb` with no outputs) loads the base model in 4-bit, trains PEFT LoRA adapters with a fixed seed, checkpoints to Google Drive, resumes, logs to W&B, and writes the adapter plus a config file.
- The same notebook merges the adapter and generates SQL for the benchmark questions (Spider held-out, Olist golden) for **both** the base model and the tuned model, into predictions JSONL files.
- `run_eval --predictions <file>` scores a predictions file with the normal step 2 comparison (guard and reader for Olist, read-only SQLite for Spider) and stores an `EvalRun` like any other, so `eval_report`, the compare API and the gate work unchanged.
- The base vs tuned comparison, training cost and the honest reading of the numbers are in `DECISION.md`.
- No new runtime dependency; image stays at or under 300 MB (296 today). Training libraries live only in the `offline` group and in the notebook.
- `backend/CLAUDE.md`, `FLOW.md`, `DECISION.md` are updated and step 7 is ticked in the root README.

**Decisions already made (owner, 2026-11-01):** train on Google Colab (free tier, T4); Weights & Biases (free personal account) for tracking; base model Qwen2.5-Coder-3B-Instruct (fall back to 1.5B if the free tier proves flaky); benchmark by generating predictions in Colab and scoring them locally from a file. Earlier standing decisions: ML dependencies stay offline, no paid LLM keys, commit locally only, never push, no `.env` files.

**Out of scope:** serving the tuned model in the product, any new provider in the live `ask`/agent path, Spider-through-agent, schema-RAG (step 8), any screen (step 9), DPO or other preference tuning, hyperparameter sweeps beyond one planned retry.

**Open questions for the owner** (recommendation first; the plan assumes the first answer):
1. *Spider `train` data:* the repo only unpacks Spider dev. Recommendation: also unpack `train_spider.json` (7,000 questions, ~140 databases disjoint from dev) into `EVAL_SPIDER_DIR` for training only; the `tune` half of dev alone is about 500 questions, too few. Needs the official Spider download once (**You**, 7.1.3).
2. *Trace cases as training data:* they hold other users' questions. Recommendation: include only `status=approved` cases whose question the reviewer saw, off by default, and not in the first run. First run is Spider only so the benchmark story is clean.
3. *Prompt format:* train on the exact `ask.prompt` system and user prompt so the tuned model is a drop-in. Recommendation: yes, with the answer wrapped in the same reply format `parse_reply` reads.

**Container budget (1/4 vCPU, 1 GiB, image 296 of 300 MB):** the only production-visible changes are one management-command flag and one pure scoring path. `torch`, `transformers`, `peft`, `trl`, `bitsandbytes`, `wandb` go in the `offline` group in `pyproject.toml` and are never imported by the Django app (a test greps for that). The image-size check runs first (7.1.1) and last (7.8.4).

**Trust model:**
- A predictions file is untrusted model output: every SQL in it goes through the same guard and reader (Olist) or read-only SQLite wall (Spider) as any model's answer. The file carries question ids and SQL only, never gold SQL or rows.
- The dataset builder reads gold SQL only to write training targets, and only from training sources; a leakage test fails if any held-out or golden question id or text is in the output.
- Secrets (W&B key, Drive token) live in Colab secrets, never in the notebook, repo or any `.env`.

Each atomic task is one small commit (Conventional Commits). **(You)** marks a task only you can do. Claude commits locally and never pushes.

---

## 7.1 Preparation

- [x] **7.1.1** Run the image-size check on the branch and record the number in `DECISION.md`. If headroom is under 3 MB, stop and trim first.
- [x] **7.1.2** Branch `feat/step-7-lora-finetune` from `feat/step-6-trace-evals` (or from `main` once step 6 is merged). *(Done by Claude when drafting.)*
- [ ] **7.1.3** **(You)** Put `train_spider.json` (from the Spider 1.0 download) next to `dev.json` in `infra/data/spider/`. `database/` already holds all 166 databases, train ones included, so nothing else is needed.
- [ ] **7.1.4** **(You)** Create a free W&B account and a Colab secret `WANDB_API_KEY`; connect Google Drive in Colab.
- [x] **7.1.5** Settings in `.env.example`, `.env.test` and settings with no defaults, plus the `.env` sync test: `FINETUNE_BASE_MODEL`, `FINETUNE_OUTPUT_DIR`, `FINETUNE_VALIDATION_FRACTION`, `FINETUNE_SEED`, `FINETUNE_MAX_EXAMPLES`. Claude does not create or edit `.env`; the owner copies the new lines.

## 7.2 Dataset builder

- [x] **7.2.1** Check that Spider train and dev databases are disjoint (by `db_id`) and that none of the held-out `db_id`s from `spider_split.json` is in the train file; fail loudly otherwise.
- [x] **7.2.2** `finetune/dataset.py`: read `train_spider.json`, build each schema text (read from the SQLite file, so `tables.json` is not needed) with the same `ask.schema` rendering used at eval time, and the training example as `(system, user, reply)` using `ask.prompt.system_prompt` and `build_prompt`; the reply is the gold SQL in the shape `parse_reply` parses. Pure functions, no model calls.
- [x] **7.2.3** Add the Spider `tune` half of dev as extra examples. Dedupe by normalized question + `db_id`. Deterministic shuffle by `FINETUNE_SEED`; split into train and validation **by database**, not by row.
- [x] **7.2.4** Optional source: approved `TraceCase` rows (off by default, flag `--include-traces`), reusing the reviewer-seen question only.
- [x] **7.2.5** Management command `build_finetune_data` writing `train.jsonl`, `validation.jsonl` and a `manifest.json` (counts, databases, seed, source flags, file hashes) to `FINETUNE_OUTPUT_DIR`. Never committed.
- [x] **7.2.6** Tests: output parses; every reply round-trips through `parse_reply`; the leakage test (no held-out `db_id`, no Olist golden question, no benchmark question text); same seed gives identical files; validation databases never appear in train.

## 7.3 Training notebook (Colab)

- [x] **7.3.1** `finetune/colab/train.ipynb`, committed without outputs, with a pinned install cell (`transformers`, `peft`, `trl`, `bitsandbytes`, `accelerate`, `datasets`, `wandb`, exact versions chosen when drafted and recorded in `DECISION.md`).
- [x] **7.3.2** Load `FINETUNE_BASE_MODEL` in 4-bit NF4 with double quantization and fp16 compute (T4 has no bf16); gradient checkpointing; LoRA on all attention and MLP projection layers; rank, alpha, dropout, learning rate, epochs and max sequence length as one config cell, with starting values and the reasons in `DECISION.md`.
- [x] **7.3.3** Train on `train.jsonl` with loss on the reply tokens only (completion-only), evaluate on `validation.jsonl` each epoch, save checkpoints to Drive every N steps, and resume from the latest on a rerun after a disconnect.
- [x] **7.3.4** W&B logging of config, loss, validation loss and GPU memory. The run name carries the git commit of the repo and the dataset manifest hash.
- [ ] **7.3.5** **(You)** Run a short smoke training (50 steps) to confirm it fits in T4 memory; report the peak memory. If the 3B model does not fit with the chosen length, drop to 1.5B and record it.
- [ ] **7.3.6** **(You)** Run the full training; keep the adapter on Drive and download `adapter/` plus `train_config.json` (Claude never needs the weights in the repo).

## 7.4 Predictions and merge (Colab)

- [x] **7.4.1** Export the benchmark questions from the repo: management command `export_benchmark` writes `bench.jsonl` with `id`, `target`, `db_id`, `question` and the **schema text only**, never gold SQL or rows, for Spider held-out and the Olist golden set.
- [x] **7.4.2** Notebook `finetune/colab/predict.ipynb`: for the **base** model and the **tuned** model (base plus adapter, merged for speed), greedy decoding (temperature 0), same prompt, write `predictions-<label>.jsonl` with `id`, `sql`, `raw_reply`, token counts, and the model label.
- [x] **7.4.3** Add `train_config.json` plus the adapter hash to each predictions file header, so a score can always be traced to a training run.
- [ ] **7.4.4** **(You)** Run both prediction passes in Colab and download the two files into `FINETUNE_OUTPUT_DIR`.

## 7.5 Score from file

- [x] **7.5.1** `evals/predictions.py`: load and validate a predictions file (header with a label, no duplicate prompts, size bounded). Answers are keyed by the SHA-256 of the exact user prompt, not by id, so a file can only answer the prompts it was generated for; `run_eval` checks coverage of every question before scoring.
- [x] **7.5.2** `run_eval --predictions <file>`: a runner that reads each answer from the file instead of calling a provider, then goes through the existing guard, execution and comparison unchanged. The `model` field of the `EvalRun` is the file's label; cost is zero; the run records the file hash.
- [ ] **7.5.3** Parity check: scoring a file built from a past Gemini run's stored predictions reproduces that run's accuracy exactly.
- [x] **7.5.4** Tests: a missing id or an unknown id is a typed error before any scoring; unguarded SQL in a file is rejected by the guard, not executed; no provider key is needed; resume and the compare API work on the resulting run.

## 7.6 Benchmark

- [ ] **7.6.1** **(You)** Score base and tuned files on Spider held-out and Olist (`make eval ARGS="--target spider --split held-out --predictions ..."`, then Olist). Exact commands are in `FLOW.md`.
- [ ] **7.6.2** Compare tuned against base with the compare API, listing flipped questions and per-cluster change; add the existing Gemini 3.5 flash-lite numbers (Olist 95.1%, Spider held-out 86.6%) as a reference row, flagged as a different kind of model.
- [ ] **7.6.3** Read the misses by hand as in step 2: separate real model errors from Spider noise, so a tuned model is not judged on noise.
- [ ] **7.6.4** Gate check: run `--gate` of tuned against base; the verdict is recorded but does not decide whether the step ships.

## 7.7 Optional trace-data round (only if time allows)

- [ ] **7.7.1** **(You)** If enough approved trace cases exist, rebuild the dataset with `--include-traces`, retrain once, and rerun 7.4 to 7.6. Evaluate on cases **not** used for training (split by cluster).
- [ ] **7.7.2** Record whether adding real traces helped; otherwise note why it was skipped.

## 7.8 Close-out

- [ ] **7.8.1** Record in `DECISION.md`: base model and why, hyperparameters, training time, W&B run link, dataset counts and manifest hash, base vs tuned numbers, the hand reading of misses, and what the tuned model does **not** prove (small benchmark, one seed, Spider noise).
- [ ] **7.8.2** `ruff`, `mypy` and the full test suite pass; a test confirms the Django app imports none of the training libraries.
- [ ] **7.8.3** `backend/openapi.json` unchanged (no API change) and checked; `API_ERRORS.md` drift test passes.
- [ ] **7.8.4** Final image-size check with CI's method; record it in `DECISION.md`.
- [ ] **7.8.5** Update `backend/CLAUDE.md` (new package, rules), `FLOW.md` (the offline training and scoring flow, exact commands), and `DECISION.md`; tick step 7 in the root README and note what remains for you.
