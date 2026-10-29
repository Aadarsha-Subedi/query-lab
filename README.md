# Querylab

> Ask your database in plain English, then measure how well the AI answered.

**Status:** In progress

Querylab is a text-to-SQL analyst agent with its own evaluation and fine-tuning loop. Visitors ask questions about a database in plain English and get a result table, the exact SQL that ran, and a replayable trace of how the agent got there. Behind it, a workbench turns those traces into an eval set, scores every model version, and benchmarks a LoRA fine-tuned model against its base.

## Roadmap

Sub-steps for each milestone will be added as they are planned.

| # | Milestone | Covers |
|---|-----------|--------|
| 0 | Foundation | Repo layout, Django + django-ninja, Neon (`querylab_app`, `querylab`, read replica), Redis, CI |
| 1 | Text-to-SQL core | Item 6: schema + question prompt, sqlglot guard, read-only replica run, confidence score, results + SQL |
| 2 | Eval harness skeleton | Item 4d: Spider with a held-out split, execution accuracy, API-model baseline |
| 3 | Agent | Item 2: plan / act / reflect, typed tools, Redis state, approval checkpoint, step logs + replay |
| 4 | Analyst UI | Landing page, chat with schema panel, approve / edit / cancel, SQL display, history |
| 5 | User workspaces | One free workspace per user: CSV upload, then manual table entry, schema-per-user isolation |
| 6 | Trace-driven evals + workbench | Item 4: trace viewer, clustering, LLM-drafted expected SQL with hand review, eval dashboard, regression gate |
| 7 | LoRA fine-tune *(time-boxed stretch)* | Item 5: instruction dataset, 4-bit load, PEFT adapters, W&B tracking, merge + benchmark |
| 8 | Schema-RAG + semantic cache *(optional)* | Retrieve table and business definitions before writing SQL; cache question → SQL |
| 9 | Deploy + portfolio polish | Hosting, public read-only eval dashboard, demo script, final results |

- [ ] 0. Foundation
- [ ] 1. Text-to-SQL core
- [ ] 2. Eval harness skeleton
- [ ] 3. Agent
- [ ] 4. Analyst UI
- [ ] 5. User workspaces
- [ ] 6. Trace-driven evals + workbench
- [ ] 7. LoRA fine-tune (stretch)
- [ ] 8. Schema-RAG + semantic cache (optional)
- [ ] 9. Deploy + portfolio polish

## Demo data

Every signed-up user gets a shared, read-only demo workspace built from the
[Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(about 100k orders, 2016 to 2018, dates shifted forward to recent months).
Licence: [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) (non-commercial).
The CSVs are downloaded into `infra/data/olist/` and never committed.
