# Querylab

> Ask your database in plain English, then measure how well the AI answered.

**Status:** In progress (steps 0, 1, 2 and 3 done in code; step 3's live-Gemini checks remain; step 4 done in code; its browser check remains; step 5 done in code; its real-Neon checks remain)

Querylab is a text-to-SQL analyst agent with its own evaluation and fine-tuning loop. Visitors ask questions about a database in plain English and get a result table, the exact SQL that ran, and a replayable trace of how the agent got there. Behind it, a workbench turns those traces into an eval set, scores every model version, and benchmarks a LoRA fine-tuned model against its base.

## Roadmap

Sub-steps for each milestone will be added as they are planned.

Steps 1 to 8 are backend-only (APIs, evals, training); every screen is built in
step 9 on the approved design system, just before deployment.

| # | Milestone | Covers |
|---|-----------|--------|
| 0 | Foundation | Repo layout, Django + django-ninja, Docker Compose, two databases + read-only reader, Redis + Huey, auth API (allauth: Google and GitHub sign-in), CI; frontend tooling and the approved design system |
| 1 | Text-to-SQL core | Item 6: schema + question prompt, sqlglot guard, read-only replica run, confidence score, results + SQL (API) |
| 2 | Eval harness skeleton | Item 4d: Spider with a held-out split, execution accuracy, API-model baseline |
| 3 | Agent | Item 2: plan / act / reflect, typed tools, Redis state, approval checkpoint, step logs + replay |
| 4 | Analyst API | The endpoints the analyst UI needs: ask, history, approve / edit / cancel, SQL + results, schema browser |
| 5 | User workspaces | The shared read-only demo plus up to 3 private workspaces per user (a schema and two login roles each, isolation proved against real roles), creating tables and editing rows, columns, keys, relations and descriptions freely, a SQL console, size and count caps; the agent answers against the workspace with the same guard, approval and replay |
| 6 | Trace-driven evals | Item 4: trace API, clustering, LLM-drafted expected SQL with hand review, eval results API, regression gate |
| 7 | LoRA fine-tune *(time-boxed stretch)* | Item 5: instruction dataset, 4-bit load, PEFT adapters, W&B tracking, merge + benchmark |
| 8 | Schema-RAG + semantic cache *(optional)* | Retrieve table and business definitions before writing SQL; cache question → SQL |
| 9 | Frontend | The whole UI, built against the contract in [`backend/FLOW.md`](backend/FLOW.md) ("The analyst screen's contract") and the generated `backend/openapi.json`: on the design system: a sign-in page (Continue with Google / GitHub) and logout, landing page, analyst chat with schema panel, approve / edit / cancel, history, workspaces + CSV upload, trace viewer, eval dashboard |
| 10 | Deploy + portfolio polish | Hosting (Cloudflare Container + static frontend), public read-only eval dashboard, demo script, final results |

- [x] 0. Foundation (your GitHub and OAuth setup tasks remain)
- [x] 1. Text-to-SQL core (your real-LLM check, 1.12.3, remains)
- [x] 2. Eval harness skeleton
- [x] 3. Agent (your live-Gemini checks remain: 3.9.2 confidence analysis, 3.10.3 Olist agent run; [plan](docs/plan/03-agent.md))
- [x] 4. Analyst API (your real-browser CORS check, 4.7.5, remains; [plan](docs/plan/04-analyst-api.md))
- [x] 5. User workspaces (now read-only copies of a `pg_dump`: [dump import plan](docs/plan/05a-dump-import.md) replaces CSV import and all table / row editing; your real-Neon checks, 5.9.7, and a real R2 round trip remain; [plan](docs/plan/05-user-workspaces.md))
- [x] 6. Trace-driven evals (backend only; your review of the first drafted batch and the live Olist agent eval, 6.9.2, remain, then 6.9.3; [plan](docs/plan/06-trace-driven-evals.md))
- [ ] 7. LoRA fine-tune (stretch; code done, data built; your remaining steps: finish the Colab training (7.3.5-7.3.6), run the prediction notebook (7.4.4), score base and tuned with `run_eval --predictions` (7.6), record the result in `DECISION.md` (7.8.1); [plan](docs/plan/07-lora-fine-tune.md))
- [ ] 8. Schema-RAG + semantic cache (optional)
- [x] 9. Frontend (built and checked against the running stack; your Google/GitHub sign-in click-through, 9.11.2, remains; [plan](docs/plan/09-frontend.md))
- [ ] 10. Deploy + portfolio polish

## Demo data

Every signed-up user gets a shared, read-only demo workspace built from the
[Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(about 100k orders, 2016 to 2018, dates shifted forward to recent months).
Licence: [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) (non-commercial).
The CSVs are downloaded into `infra/data/olist/` and never committed.
