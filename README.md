# Multi-Agent Data Quality Pipeline

![CI](https://github.com/chrisandrews1012/data-quality-pipeline/actions/workflows/ci.yml/badge.svg)
![GitHub last commit](https://img.shields.io/github/last-commit/chrisandrews1012/data-quality-pipeline)
![Python Version](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?logo=fastapi&logoColor=white)
![PydanticAI](https://img.shields.io/badge/PydanticAI-latest-blueviolet)
![Claude](https://img.shields.io/badge/Claude-Sonnet%204.6-orange?logo=anthropic&logoColor=white)

Upload a CSV and get back a cleaned version, a full quality report, and a complete list of every issue found and fixed. Built on a four-agent system powered by Claude Sonnet 4.6, with each agent handling a single responsibility and passing a typed result to the next.

## Problem Statement

Raw data is rarely clean. Missing values, inconsistent formatting, duplicate records, and out-of-range values are endemic to real-world datasets, and no single fix works for all of them. A single model cannot reliably handle all of this in one pass. Breaking the problem into discrete agents, each with a specific role and a typed contract with the next, keeps failures catchable and the output trustworthy.

## How It Works

Four agents run in sequence, each handing its typed output to the next.

**Profiler** reads the dataset and infers what each column actually is: an age, an email, a currency amount, a category, etc. Missing value patterns are analysed statistically to determine whether gaps are random (MCAR/MAR) or systematic (MNAR).

**Validator** looks at what the Profiler found and decides which rules apply to each column. An age column gets range checks, an email column gets format checks, a categorical column gets case consistency checks. Nothing is hardcoded: the rules adapt to whatever columns are present.

**Repairer** fixes what it can. Duplicates are dropped, currency symbols are stripped, dates are standardised, and nulls are imputed. Columns classified as MNAR are left untouched and escalated for manual review, since imputing them would silently bias the data.

**Reporter** writes up everything that was found and fixed into a structured Markdown report.

```
CSV input
    │
    ▼
Profiler   →  DataProfile
    │
    ▼
Validator  →  ValidationReport
    │
    ▼
Repairer   →  RepairReport + cleaned CSV
    │
    ▼
Reporter   →  Markdown report
```

## Example Output

Running the pipeline on the included HR dataset (520 rows, 9 columns):

```
Profiler complete: 520 rows, 9 columns, 20 duplicates
Validator complete: Critical issues found | 9 rules applied | 6 findings
Repairer complete: 10 repairs, 20 rows dropped, 1 unresolved
Reporter complete: report saved to docs/data_quality_report.md
```

**Before / After:**

| Metric | Before | After |
|---|---|---|
| Row count | 520 | 441 |
| Null count | 84 | 0 |
| Duplicate rows | 20 | 0 |

**Repair actions applied:**

| Column | Issue | Action |
|---|---|---|
| (all columns) | 20 duplicate rows | Dropped |
| salary | Currency symbols (`$50,000`) | Stripped to `50000.0` |
| salary | 12 null values | Imputed with median |
| age | 3 values outside 0–120 | Nullified then median imputed |
| hire_date | Mixed date formats | Standardised to `YYYY-MM-DD` |
| department | Mixed casing (`engineering`, `SALES`) | Normalised to title case |
| gender | Mixed casing (`male`, `Male`) | Normalised to title case |

**Unresolved (escalated for manual review):**

```
'email' (email): 18 null values. Whether to drop or keep these rows depends on whether email is required downstream. Manual review required.
```

## Validation

The pipeline uses three layers of validation to ensure the LLM produces correct results, not just structurally valid ones.

### Layer 1: Schema Validation (Pydantic)

Every agent returns a typed Pydantic model. Structural errors fail immediately at parse time. Model validators also prevent count hallucinations: if the LLM claims six failures but returns nine, the count is corrected automatically before it can propagate.

### Layer 2: Invariant Checks

After each agent, deterministic checks compare LLM claims against ground truth computed directly from the DataFrame. Any violation raises `InvariantViolation` and halts the run. Examples of what gets caught: a claimed row count that doesn't match the file, an invented column name, `passed=True` alongside a critical failure, or a `rows_dropped` value that doesn't match the actual output CSV.

### Layer 3: Golden Dataset Evals

The eval runner in `evals/runner.py` runs the full pipeline against four synthetic datasets covering a range of data quality scenarios, from fully clean to heavily corrupted. Each dataset has a known-facts spec that the pipeline output is scored against. All four datasets currently pass:

| Dataset | Factual Accuracy | Semantic Types | Repair Coverage | Unresolved | MNAR Safety | No False Positives | Overall |
|---|---|---|---|---|---|---|---|
| hr | PASS | 9/9 (100%) | 5/5 | 1/1 | N/A | — | PASS |
| hr_clean | PASS | 9/9 (100%) | 0/0 | — | N/A | PASS | PASS |
| ecommerce | PASS | 8/8 (100%) | 4/4 | 1/1 | N/A | — | PASS |
| medical | PASS | 8/8 (100%) | 4/4 | 1/1 | PASS | — | PASS |

The four datasets are designed to cover different failure modes:

| Dataset | Description |
|---|---|
| `hr_messy` | HR records with nulls, duplicates, currency symbols, mixed date formats, and mixed casing |
| `hr_clean` | Same HR schema with zero injected issues. The pipeline must produce zero repairs. |
| `ecommerce` | Order records with different column names than HR. Tests that the pipeline generalizes beyond a single domain. |
| `medical` | Patient records with MNAR missingness. The pipeline must detect it and refuse to impute. |

Run evals manually with `make eval`. Results are written to `evals/results/scorecard.md`.

## How to Run

An Anthropic API key is required. Get one at [console.anthropic.com](https://console.anthropic.com).

```bash
git clone https://github.com/chrisandrews1012/data-quality-pipeline.git
cd data-quality-pipeline
cp .env.example .env   # add your ANTHROPIC_API_KEY
```

**Web interface**

```bash
docker compose up
```

Open [http://localhost:8000](http://localhost:8000). Upload any CSV and the pipeline runs in the browser with live progress, an inline report, and a download button for the cleaned file.

**Command line**

```bash
uv sync
make run     # Run the pipeline on the included HR sample dataset
make serve   # Start the web interface without Docker
```

To run on your own CSV:

```bash
uv run python -m src.data_quality_pipeline.pipeline path/to/your/data.csv
```

## Testing

**Generate synthetic datasets** (required before running evals or `make run`):

```bash
make data
```

This generates all four datasets in `data/raw/` using fixed random seeds, so results are reproducible.

**Run the test suite:**

```bash
make test-fast   # 73 deterministic tests, no API key required (~4s)
make test-llm    # LLM integration tests, requires ANTHROPIC_API_KEY
make eval        # Golden dataset evals across all four datasets
```

The 73 fast tests require no API key and cover three areas:

```
tests/test_invariants.py   22 tests   invariant checks for all three agents
tests/test_repairer.py     16 tests   repair logic for every column type
tests/test_tools.py        35 tests   date parsing, currency cleaning, email validation
```

LLM tests (`test_profiler.py`, `test_validator.py`) are marked with `pytest.mark.llm` and excluded from `make test-fast`. They call the live API and verify end-to-end agent behaviour.

## File Structure

```
data-quality-pipeline/
├── .github/
│   └── workflows/
│       └── ci.yml
├── data/
│   ├── external/
│   ├── interim/
│   ├── processed/
│   ├── raw/
│   │   ├── hr_messy.csv
│   │   ├── hr_clean.csv
│   │   ├── ecommerce_messy.csv
│   │   └── medical_messy.csv
│   ├── generate_hr.py
│   ├── generate_hr_clean.py
│   ├── generate_ecommerce.py
│   └── generate_medical.py
├── docs/
│   ├── architecture.md
│   └── data_quality_report.md
├── evals/
│   ├── expected/
│   │   ├── hr_expected.json
│   │   ├── hr_clean_expected.json
│   │   ├── ecommerce_expected.json
│   │   └── medical_expected.json
│   ├── results/
│   └── runner.py
├── logs/
├── src/
│   └── data_quality_pipeline/
│       ├── agents/
│       │   ├── profiler.py
│       │   ├── validator.py
│       │   ├── repairer.py
│       │   └── reporter.py
│       ├── invariants.py
│       ├── jobs.py
│       ├── models.py
│       ├── pipeline.py
│       ├── server.py
│       └── tools.py
├── static/
│   └── index.html
├── tests/
│   ├── conftest.py
│   ├── test_invariants.py
│   ├── test_repairer.py
│   ├── test_tools.py
│   ├── test_profiler.py
│   └── test_validator.py
├── .dockerignore
├── .env.example
├── .python-version
├── docker-compose.yml
├── Dockerfile
├── main.py
├── Makefile
└── pyproject.toml
```
