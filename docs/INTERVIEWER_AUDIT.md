# Strict NxtWave Interviewer Audit

Audit date: 4 September 2026

Scope: source, tests, configuration, documentation, graph topology, ignored files, credential
handling, locally executable checks, and both documented live Gemini workflows. Generated
artifacts were inspected after each live run.

## Outcome

- **CRITICAL findings remaining:** 0
- **HIGH findings remaining:** 0
- **MEDIUM findings remaining:** 1, explicitly disclosed and requiring a larger evaluation
  programme rather than a code correctness fix
- **LOW findings remaining:** 1 deliberate scope boundary

## Zero-cost provider revision

The original OpenAI provider was replaced—not supplemented—with Gemini as the single production
provider after the user required zero API spend. `gemini-3.7-flash` is the default because Google's
current pricing page lists free input and output tokens within Free Tier limits. The project uses
Gemini's native JSON-schema structured output and retains the same Pydantic validation and provider
protocol. An account-bound key was configured locally and used to verify both workflows without
placing the credential in source control or generated artifacts.

## Findings and dispositions

### CRITICAL

No critical finding was identified. In particular, the audit did not find fake evaluator routing,
hard-coded demo verdicts, LLM-owned overall acceptance, an infinite graph path, or committed
credentials.

### HIGH — fixed

1. **The environment setting could originally raise workflow retries above the assessment's
   required maximum of two.**
   - Risk: a configuration value could violate the cost and termination contract even though the
     default was correct.
   - Fix: `MAX_WORKFLOW_RETRIES = 2` is enforced in `Settings.validate_for_live_run` and again in the
     direct `LessonWorkflow` constructor.
   - Evidence: the configuration test rejects `WORKFLOW_MAX_RETRIES=3`; routing tests verify the
     exact attempt 1 → 2 → 3 boundary.

2. **A retry originally received evaluation feedback but not the prior draft it was told to
   revise.**
   - Risk: feedback was genuinely used, but “preserve accurate content” was not fully actionable
     without the draft.
   - Fix: the prior lesson is now supplied in an escaped `<previous_lesson>` data boundary alongside
     `<revision_feedback>`.
   - Evidence: the workflow test asserts that both the failed reason/correction and complete prior
     draft reach the second generation prompt.

### MEDIUM — open and disclosed

1. **The LLM judge has no human-labelled calibration dataset.**
   - Impact: false passes and false failures are possible even with a strong explicit rubric and
     native structured output.
   - Mitigation implemented: six independent hard checkpoints, deterministic aggregation, an
     isolated objective completeness guard, full evidence logs, and bounded retries.
   - Production path: labelled eval examples, adversarial regression cases, judge calibration or
     ensembles, and human escalation.

### LOW — accepted scope boundary

1. **The topic parameter is generic, but the detailed coverage contract is intentionally optimized
   for the assessment's RAG lesson.**
   - Rationale: the graph, state, provider, evaluator schema, memory, and persistence accept another
     topic, but a serious production lesson for that topic should supply a versioned topic-specific
     coverage rubric. Adding a curriculum platform would violate the assessment's minimal-scope
     direction.

## Requirement audit matrix

| Area | Evidence | Result |
|---|---|---|
| Greenfield, compact Python repository | `pyproject.toml`, `src/lesson_generator`, initialized Git repository | PASS |
| Real LangGraph workflow | Five compiled nodes, two conditional edges, feedback loop | PASS |
| Explicit typed state | `LessonState` contains topic, attempts, history, feedback, memory, status, demo, trace | PASS |
| Structured hard evaluator | Pydantic `LessonEvaluation`, six independent booleans, forbidden extras | PASS |
| Strong explicit rubric | Rubric v1.1.0 defines PASS and common FAIL conditions per criterion | PASS |
| Deterministic acceptance | `overall_pass = all(...)`; route reads only that property | PASS |
| Hybrid validation | Semantic judge plus empty/undersized objective guards; no keyword score | PASS |
| Feedback-driven regeneration | Reason, evidence, correction, and previous draft reach retry prompt | PASS |
| Two-retry bound | Hard cap in configuration and workflow; attempt 3 routes to exhaustion | PASS |
| Guaranteed finite graph | Deterministic bound plus LangGraph recursion limit | PASS |
| History and rejection evidence | Every draft/evaluation plus one log row per failed criterion | PASS |
| Persistent memory | SQLite append/write, aggregate/read, generator prompt injection | PASS |
| Bounded self-evolution | Fixed guidance templates; no code/prompt/rubric rewriting | PASS |
| Deliberate-error integrity | Content injected only on attempt 1; evaluator receives no demo flag | PASS |
| Demo-memory isolation | Artificial failures stored but excluded by `WHERE demo_mode = 0` | PASS |
| Model/provider configuration | Shared Gemini boundary; env key/model; timeout and transport retries | PASS |
| Prompt/content boundaries | System/user separation and HTML-escaped data tags | PASS |
| CLI observability | Attempts, criteria, reasons, decisions, memory, status, paths | PASS |
| Output persistence | Atomic per-file writes; stable latest paths and run-specific preservation | PASS |
| Missing/malformed behavior | Early credential error, malformed structured response error, empty response error | PASS |
| Deterministic tests | 24 tests; no API calls | PASS |
| Documentation | README, matching Mermaid graph, commands, limitations, Loom script | PASS |
| Secret hygiene | `.env` ignored; `.env.example` tracked candidate; no key-like value found | PASS |
| Live normal run | Run `4697a65785824f4e882c2a3dbe162090`; Gemini 3.6; rubric v1.1.0; six criteria passed on attempt 1 | PASS |
| Live deliberate-error run | Run `7ddc690631ec447d927877512bb592de`; current Gemini 3.7 default; seeded misconception failed attempt 1 and corrected attempt 2 passed | PASS |

## Verification evidence

Commands run after the HIGH fixes:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check demo.py src tests
.\.venv\Scripts\python.exe -m compileall -q demo.py src tests
.\.venv\Scripts\python.exe demo.py --topic "Introduction to RAG"
.\.venv\Scripts\python.exe demo.py --topic "Introduction to RAG" --inject-error
```

Observed results:

```text
24 passed in 0.83s
All checks passed!
compileall exit code 0
normal: PASSED, 1 attempt, all six criteria passed
deliberate-error: PASSED, 2 attempts; Technical Accuracy alone failed first, then all six passed
```

The normal 3.6 snapshot is preserved under
`outputs/runs/4697a65785824f4e882c2a3dbe162090/`. The current 3.7 deliberate-error snapshot and
stable latest-run files are under `outputs/runs/7ddc690631ec447d927877512bb592de/`
and `outputs/`; the earlier 3.6 demo evidence also remains preserved.
Their summaries, histories, rejection logs, final lessons, schema consistency, and secret hygiene
were inspected. One earlier evaluator request received Gemini's temporary `503 UNAVAILABLE`
high-demand response; the unchanged workflow completed successfully when retried.

A post-run human review identified wording that could imply RAG itself guarantees safe private-data
handling. The generator requirements and Technical Accuracy rubric were hardened and versioned as
1.1.0, a regression test was added, and both live modes were rerun successfully under that version.

The compiled graph's own Mermaid output was also inspected. It contained exactly the expected
`START → load_memory → generate → evaluate`, pass/fail branches, retry/exhausted branches, and
`finalize → END` topology documented in the README.

A later run under the interactive Windows account exposed an ACL conflict in pytest's default
global temporary directory. Pytest now uses the ignored project-local `.pytest-tmp/` directory
with its optional cache disabled; the complete 24-test suite passed under that account.

## Final audit judgment

The repository demonstrates authentic generation, structured semantic evaluation, deterministic
quality gating, feedback-driven revision, durable bounded adaptation, and observable finite
control flow without unnecessary infrastructure. Deterministic tests and both live modes are
verified. The remaining material limitation is judge calibration, not workflow correctness.
