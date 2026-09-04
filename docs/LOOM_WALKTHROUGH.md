# Loom Walkthrough: 15–20 Minutes

Use a face-visible layout with the terminal and editor readable beside the camera. Run both live
commands before recording, confirm billing/quotas, and clear or archive old `outputs/` files so the
artifacts shown belong to the recorded run. Do not show `.env` or any API key.

## 0–2 min — Problem and objective

- **Show:** `README.md`, sections “Problem” through “Solution Overview”.
- **Command:** none.
- **Explain:** A single generation prompt is probabilistic. The assessment requires an observable
  generate → evaluate → decide → regenerate workflow for a specific beginner audience.
- **Point out:** Six hard criteria, Python-owned acceptance, two-retry maximum, and saved evidence.
- **Key statement to understand:** “The system does not assume generation quality; it makes quality
  a tested state transition.”

## 2–5 min — Architecture and real LangGraph

- **Show:** the Mermaid diagram in `README.md`, then `src/lesson_generator/graph.py`.
- **Command:** optional graph source check:

  ```powershell
  Select-String -Path src\lesson_generator\graph.py -Pattern "add_node|add_edge|add_conditional_edges"
  ```

- **Explain:** `load_memory`, `generate`, `evaluate`, `record_failure`, and `finalize` are the only
  nodes. The first conditional edge uses deterministic overall acceptance; the second uses the
  retry counter.
- **Point out:** the loop from `record_failure` to `generate`, both exits to `finalize`, and the
  explicit recursion limit.
- **Key statement to understand:** “Agentic behavior comes from evaluated feedback and a conditional
  loop, not from multiplying agent classes.”

## 5–7 min — State, prompts, evaluator, and routing

- **Show:** `src/lesson_generator/state.py`, `schemas.py`, `rubric.py`, and the two prompt builders in
  `prompts.py`.
- **Command:** none.
- **Explain:** State contains every important value. Each criterion is a validated
  `CriterionResult`; a failed criterion must include improvement feedback. Topic and lesson text
  are delimited untrusted content.
- **Point out:** `LessonEvaluation.overall_pass`, `extra="forbid"`, rubric version `1.1.0`, and the
  independent evaluator system prompt.
- **Key statement to understand:** “The LLM judges semantic criteria; Python applies `all(...)` and
  controls whether the graph terminates.”

## 7–10 min — Normal live workflow

- **Show:** terminal, then the four latest files under `outputs/`.
- **Command:**

  ```powershell
  .\.venv\Scripts\python.exe demo.py --topic "Introduction to RAG"
  ```

- **Explain:** Memory loads first. Watch the attempt number, each criterion, overall result, final
  status, and artifact paths. A high-quality first attempt may pass; a failure may legitimately
  exercise revision.
- **Point out:** Only claim the status printed in this run. Open `outputs/final_lesson.md` and scan
  the RAG pipeline, training/fine-tuning distinction, example, and limitations.
- **Key statement to understand:** “A PASS means every required criterion passed; it is never an
  averaged score.”

## 10–14 min — Deliberate-error demonstration

- **Show:** `DEMO_MISCONCEPTION` and the guarded injection in `generator.py`; keep `evaluator.py` and
  the terminal available.
- **Command:**

  ```powershell
  .\.venv\Scripts\python.exe demo.py --topic "Introduction to RAG" --inject-error
  ```

- **Explain:** Only attempt 1 receives a false claim that retrieval changes model weights. No demo
  flag reaches `LessonEvaluator`, so the production judge must detect the content using the normal
  technical-accuracy rubric.
- **Point out:** Attempt 1 technical accuracy FAIL, its reason/evidence/correction, the regeneration
  message, attempt 2, and the actual final status. If the judge does not catch it, say so honestly
  and do not present that run as a successful detection.
- **After the run, show:**

  ```powershell
  Get-Content outputs\evaluation_history.json
  Get-Content outputs\rejection_log.json
  ```

- **Key statement to understand:** “The test mechanism injects content, never a verdict; the same
  real evaluator handles normal and demo lessons.”

## 14–16 min — Persistent memory and bounded self-evolution

- **Show:** `src/lesson_generator/memory.py`, especially the table, aggregation query, fixed
  guidance templates, and `WHERE demo_mode = 0`.
- **Command:** run normal mode again if the first normal run recorded a genuine failure:

  ```powershell
  .\.venv\Scripts\python.exe demo.py --topic "Introduction to RAG"
  ```

- **Explain:** Normal failure evidence is appended to SQLite. A later run loads the highest-count
  patterns and adds auditable guidance to generation. Artificial demo evidence is retained but
  excluded from adaptation.
- **Point out:** “Persistent memory loaded” in terminal and `memory_guidance` in
  `outputs/run_summary.json`.
- **Key statement to understand:** “Self-evolution is constrained to evidence plus fixed guidance;
  the system cannot rewrite prompts, rubric, security rules, or code.”

## 16–18 min — Tests, logs, and robustness

- **Show:** `tests/test_workflow.py`, `test_schemas_and_evaluator.py`, and `test_memory.py`.
- **Commands:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest
  .\.venv\Scripts\ruff.exe check demo.py src tests
  .\.venv\Scripts\python.exe -m compileall -q demo.py src tests
  ```

- **Explain:** Tests use a provider protocol and deterministic fakes, so they require no paid calls.
  They cover semantic-interface traversal in demo mode, exact retry exhaustion, malformed schema,
  missing credentials, persistence, and feedback propagation.
- **Point out:** the actual pass count from the current run, not the historical README snapshot.
- **Key statement to understand:** “Transport retries and lesson-quality retries are separate
  controls: the provider handles transient calls; the graph handles rejected content.”

## 18–20 min — Trade-offs, limitations, and close

- **Show:** README “Design Decisions”, “Limitations”, and “Production Improvements”, then
  `docs/INTERVIEWER_AUDIT.md`.
- **Command:** none.
- **Explain:** SQLite and a CLI are deliberate scope choices. LLM-as-judge is useful but not fully
  calibrated. Production work would add labelled evals, judge calibration/ensembles, metrics,
  human escalation, and CI gates.
- **Point out:** no vector database, frontend, or autonomous prompt rewriting was added because none
  improves the assessment's core proof.
- **Key statement to understand:** “This submission optimizes for auditable control around
  probabilistic behavior, not feature count.”

## Questions you should be ready to answer

1. **Why not let the judge return `overall_pass`?** It would give a probabilistic component control
   of termination and could contradict its own criterion results.
2. **Why store full drafts in evaluation history?** It makes evidence and revision behavior
   reproducible instead of retaining only scores.
3. **Why no vector database?** The memory is a small structured aggregation problem, and SQLite is
   more transparent and sufficient.
4. **Can the demo be faked?** The injection is deterministic, but the verdict is not. The evaluator
   gets no demo flag; saved history shows its actual result.
5. **What if every attempt fails?** Attempt 3 is saved with `FAILED_AFTER_MAX_RETRIES`; the system
   never labels it approved.
6. **Does memory rewrite the prompt?** It adds derived context to a stable prompt template. It
   cannot edit the template, rubric, or code.
7. **What does the 500-character check prove?** Only that a draft is not grossly incomplete. The
   judge still owns semantic accuracy, clarity, examples, terminology, coverage, and flow.
