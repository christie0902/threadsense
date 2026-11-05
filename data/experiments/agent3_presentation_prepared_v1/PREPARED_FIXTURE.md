# Prepared presentation fixture (not model output)

Zero-call scripted overnight run (`SCRIPTED_MOCK`) over five work items, built to demonstrate AdviceCard v4
(`details`, `next_step`) in the dashboard. Responses: `tests/fixtures/agent3_presentation_prepared_responses.json`.

- Drafts and grounding responses are the recorded live ones from `data/experiments/agent3_e2e_eval_v1/run`
  (prompts v17), with hand-written summary rewrites and detail sentences, and hand-set verdicts for every new or
  rewritten statement (their rationales start with `PREPARED`).
- Submit detail sentence 4 is deliberately unsupported; sentence 5 depends on it and is withheld by that dependency.
- Says nothing about live writing quality under prompts v18. A live evaluation needs separate authorization.
