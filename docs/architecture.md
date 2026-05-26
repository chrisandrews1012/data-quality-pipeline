# Pipeline Architecture

## Overview

The data quality pipeline is a four-agent system built on PydanticAI. Each agent receives structured input, calls an LLM with a focused prompt, and returns a typed Pydantic model. The pipeline runs agents in sequence: Profiler, Validator, Repairer, Reporter.

```
CSV input
    │
    ▼
Profiler      →  DataProfile
    │
    ▼
Validator     →  ValidationReport
    │
    ▼
Repairer      →  RepairReport + cleaned CSV
    │
    ▼
Reporter      →  Markdown report
```

## Agents

### Profiler

The Profiler reads the raw CSV, computes statistics with pandas, then asks the LLM to classify each column's semantic type (id, email, age, date, currency, categorical, numeric, text, boolean, unknown) and write a plain-English summary.

The pandas statistics (row count, null counts, unique counts, sample values) are computed deterministically before the LLM call. The LLM only adds meaning: type labels and narrative.

### Validator

The Validator receives the full DataProfile and asks the LLM to identify data quality rules and check them against the profile. It returns a list of ValidationFailures, each with a severity level: critical, consideration, or info.

The `passed` field is true only when zero critical failures are found. A model validator enforces this at parse time so the LLM cannot return `passed=True` alongside critical failures.

For rules that apply to the whole dataset rather than one column (such as duplicate rows), the column field must be `"(all columns)"`. The system prompt makes this convention explicit to prevent the LLM from inventing other labels.

### Repairer

The Repairer works in two steps. First, the LLM reads the ValidationReport and decides what action to take for each failure: impute, reformat, cap, flag, or skip. Second, `apply_repairs()` executes those decisions as pure Python against the actual DataFrame. The LLM produces intent; the Python function produces the file.

This separation means repair logic is fully testable without calling the LLM, and the output CSV is always consistent with what the RepairReport claims.

MNAR columns (missingness not at random) are never imputed. The Repairer escalates them to the unresolved list regardless of what other agents suggested.

### Reporter

The Reporter receives the full PipelineContext (profile, validation, repair) and writes a structured Markdown report. It is the only agent with no invariant checks: its output is narrative and cannot be fact-checked the same way counts and column names can.

## Key Design Decisions

**Structured output over free text.** Every agent returns a Pydantic model, not a string. This makes downstream processing reliable and keeps validation straightforward.

**LLM for semantics, pandas for facts.** Statistics that can be computed deterministically are computed before the LLM call. The LLM adds labels and judgments; it does not count rows or nulls.

**Repairs are executed in Python.** The LLM decides what to do; `apply_repairs()` does it. This avoids code-execution risks and makes repair behavior unit-testable.

**MNAR safety.** Imputing MNAR columns is statistically harmful because the missingness itself carries information. The pipeline detects MNAR columns via Little's MCAR test and point-biserial correlation, then blocks imputation regardless of LLM intent.

---

## Validation Strategy

The pipeline uses three validation layers. Each layer catches a different class of error.

### Layer 1: Schema Validation (Pydantic)

Pydantic validates structure at parse time. If the LLM returns the wrong type for a field or omits a required field, the parse fails immediately.

Two model validators correct derived counts before they can propagate:

- `ValidationReport._fix_failure_count` sets `failure_count = len(self.failures)`
- `RepairReport._fix_total_repairs` sets `total_repairs = len(self.actions)`

These validators prevent count hallucinations. The LLM cannot claim six failures when nine are present.

### Layer 2: Invariant Checks (Deterministic)

Invariant checks run after each agent and compare LLM claims against ground truth computed from the actual DataFrame. They catch factual errors that pass schema validation.

Three check functions are defined in `src/data_quality_pipeline/invariants.py`:

| Function | What it checks |
|---|---|
| `check_profile_invariants` | row count, column count, null counts, duplicate count, column name set |
| `check_validation_invariants` | failure count matches list length, passed reflects critical failures, all column names exist |
| `check_repair_invariants` | total repairs matches action count, rows dropped matches actual row delta, all column names exist |

Any violation raises `InvariantViolation`, which halts the pipeline for that dataset. The eval runner catches this exception and records it as a factual accuracy failure rather than crashing the full run.

### Layer 3: Golden Dataset Evals

The eval runner in `evals/runner.py` runs the full pipeline against known datasets and scores the output against expected specs in `evals/expected/`.

Each spec defines:

- `known_facts`: exact row count, duplicate count, and null count
- `expected_column_types`: the semantic type each column should receive
- `must_repair`: columns and issue types the repairer must address
- `must_flag_unresolved`: columns that cannot be auto-repaired and must be escalated
- `must_not_impute_mnar`: whether MNAR safety is required
- `expect_zero_repairs`: for clean datasets, asserts the repairer applies no actions

Results are written to `evals/results/scorecard.md` after every run. Run with `make eval`.

### Datasets

| Dataset | Purpose |
|---|---|
| `hr_messy.csv` | Core HR dataset with injected nulls, mixed formats, duplicates |
| `hr_clean.csv` | Same schema, zero issues. Tests that the pipeline produces no false positives |
| `ecommerce_messy.csv` | Different column names (price, status, order_date). Tests generalization |
| `medical_messy.csv` | Sparse notes column, out-of-range values, MNAR missingness test |

### Test Layers

| Command | What runs |
|---|---|
| `make test-fast` | Deterministic unit tests only, no LLM calls |
| `make test-llm` | LLM-backed integration tests |
| `make eval` | Full golden dataset evaluation |

Fast tests cover `apply_repairs()` and all invariant check functions. They run in seconds and require no API key.
