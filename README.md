# Multi-Agent Data Quality Pipeline

![GitHub last commit](https://img.shields.io/github/last-commit/chrisandrews1012/data-quality-pipeline)
![GitHub repo size](https://img.shields.io/github/repo-size/chrisandrews1012/data-quality-pipeline)
![Python Version](https://img.shields.io/badge/python-3.12-blue)
![PydanticAI](https://img.shields.io/badge/PydanticAI-Claude%20Sonnet%204.6-blueviolet)

A dataset-agnostic multi-agent pipeline that profiles, validates, repairs, and documents data quality issues in arbitrary tabular datasets.

## Problem Statement

Raw data is rarely clean. Missing values, inconsistent formatting, duplicate records, and out-of-range values are endemic to real-world datasets, and each requires different reasoning to fix correctly. A single model cannot reliably handle all of this in one pass. The challenge is decomposing the problem into discrete, auditable steps, each with a typed contract between agents so failures are catchable and the output is trustworthy.

## Approach

Four agents run in sequence. Each receives the typed output of the previous one via Pydantic models, so the pipeline fails loudly if any agent produces malformed output.

- **Profiler** (`claude-sonnet-4-6`): receives pre-computed column statistics and infers a semantic type for each column (`id`, `email`, `age`, `date`, `currency`, `categorical`, `numeric`, `boolean`, `text`). Missingness analysis (MCAR/MAR/MNAR via Little's test and correlation checks) is computed deterministically in Python and attached after the LLM call so the agent handles reasoning, not arithmetic.
- **Validator** (`claude-sonnet-4-6`): reads the DataProfile and infers appropriate validation rules per column based on semantic type, then applies them. MNAR columns are always escalated to critical severity since imputation would bias results.
- **Repairer**: repairs are applied in Python, driven by the inferred semantic types from the profile. MNAR columns and columns above 50% null are skipped. The LLM receives a summary of what was done and produces a structured RepairReport with reasoning for each action.
- **Reporter** (`claude-sonnet-4-6`): receives the full PipelineContext (profile + validation + repair) and writes a markdown data quality report.

## Results

On the included synthetic HR dataset (520 rows, 9 columns):

| Metric | Before | After |
|---|---|---|
| Row Count | 520 | 441 |
| Null Count | 84 | 0 |
| Duplicate Rows | 20 | 0 |

10 repair actions were applied across 7 columns: duplicate removal, row drops for invalid emails, out-of-range age nullification with median imputation, currency symbol stripping, date format standardization, and categorical case normalization. See `docs/data_quality_report.md` for the full report from the last run.

## How to Run

```bash
git clone https://github.com/chrisandrews1012/data-quality-pipeline.git
cd data-quality-pipeline
uv sync
cp .env.example .env  # add your ANTHROPIC_API_KEY
```

```bash
make data   # Generate synthetic messy dataset
make run    # Run the full four-agent pipeline
make test   # Run the test suite
```

> **Note:** The synthetic dataset and a sample report are included in the repo, so `make data` can be skipped unless you want to regenerate fresh data.

The pipeline writes the cleaned CSV to `data/processed/cleaned_data.csv` and the markdown report to `docs/data_quality_report.md`.

**Running on your own data**

```bash
uv run python -m src.data_quality_pipeline.pipeline path/to/your/data.csv
```

The pipeline adapts to whatever columns are present, profiling and repairing based on inferred semantic types.

## File Structure

```
data-quality-pipeline/
├── data/
│   ├── raw/
│   │   └── messy_data.csv
│   ├── processed/
│   │   └── cleaned_data.csv
│   └── generate_synthetic.py
├── docs/
│   └── data_quality_report.md
├── src/
│   └── data_quality_pipeline/
│       ├── agents/
│       │   ├── profiler.py
│       │   ├── validator.py
│       │   ├── repairer.py
│       │   └── reporter.py
│       ├── models.py
│       ├── pipeline.py
│       └── tools.py
├── tests/
│   ├── conftest.py
│   ├── test_profiler.py
│   ├── test_tools.py
│   └── test_validator.py
├── .python-version
├── Makefile
├── pyproject.toml
└── uv.lock
```
