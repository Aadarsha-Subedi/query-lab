# Querylab

> Ask your database in plain English, then measure how well the AI answered.

**Status:** In progress (step 0 done; step 1 next)

Querylab is a text-to-SQL analyst agent with its own evaluation and fine-tuning loop. Visitors ask questions about a database in plain English and get a result table, the exact SQL that ran, and a replayable trace of how the agent got there. Behind it, a workbench turns those traces into an eval set, scores every model version, and benchmarks a LoRA fine-tuned model against its base.

## Roadmap

Sub-steps for each milestone will be added as they are planned.

Steps 1 to 8 are backend-only (APIs, evals, training); every screen is built in
step 9 on the approved design system, just before deployment.

| # | Milestone | Covers |
|---|-----------|--------|
| 0 | Foundation | Repo layout, Django + django-ninja, Docker Compose, two databases + read-only reader, Redis + Huey, auth API (allauth), CI; frontend tooling and the approved design system |
| 1 | Text-to-SQL core | Item 6: schema + question prompt, sqlglot guard, read-only replica run, confidence score, results + SQL (API) |
| 2 | Eval harness skeleton | Item 4d: Spider with a held-out split, execution accuracy, API-model baseline |
| 3 | Agent | Item 2: plan / act / reflect, typed tools, Redis state, approval checkpoint, step logs + replay |
| 4 | Analyst API | The endpoints the analyst UI needs: ask, history, approve / edit / cancel, SQL + results, schema browser |
| 5 | User workspaces | One free demo workspace per user (`GET /api/workspaces`), CSV upload, then manual table entry, schema-per-user isolation, the per-user workspace limit |
| 6 | Trace-driven evals | Item 4: trace API, clustering, LLM-drafted expected SQL with hand review, eval results API, regression gate |
| 7 | LoRA fine-tune *(time-boxed stretch)* | Item 5: instruction dataset, 4-bit load, PEFT adapters, W&B tracking, merge + benchmark |
| 8 | Schema-RAG + semantic cache *(optional)* | Retrieve table and business definitions before writing SQL; cache question → SQL |
| 9 | Frontend | The whole UI on the design system: auth screens (login, signup, verify email, Google / GitHub, logout), landing page, analyst chat with schema panel, approve / edit / cancel, history, workspaces + CSV upload, trace viewer, eval dashboard |
| 10 | Deploy + portfolio polish | Hosting (Cloudflare Container + static frontend), public read-only eval dashboard, demo script, final results |

- [x] 0. Foundation (your GitHub and OAuth setup tasks remain)
- [ ] 1. Text-to-SQL core
- [ ] 2. Eval harness skeleton
- [ ] 3. Agent
- [ ] 4. Analyst API
- [ ] 5. User workspaces
- [ ] 6. Trace-driven evals
- [ ] 7. LoRA fine-tune (stretch)
- [ ] 8. Schema-RAG + semantic cache (optional)
- [ ] 9. Frontend
- [ ] 10. Deploy + portfolio polish

## Demo data

Every signed-up user gets a shared, read-only demo workspace built from the
[Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(about 100k orders, 2016 to 2018, dates shifted forward to recent months).
Licence: [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) (non-commercial).
The CSVs are downloaded into `infra/data/olist/` and never committed.
