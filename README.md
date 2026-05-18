# Multi-Agent Data Quality Pipeline

![GitHub last commit](https://img.shields.io/github/last-commit/chrisandrews1012/data-quality-pipeline)
![GitHub repo size](https://img.shields.io/github/repo-size/chrisandrews1012/data-quality-pipeline)
![Python Version](https://img.shields.io/badge/python-3.12-blue)
![PydanticAI](https://img.shields.io/badge/PydanticAI-Claude%20Sonnet%204.6-blueviolet)

Upload a CSV and get back a cleaned version, a full quality report, and a complete list of every issue found and fixed. Built on a multi-agent system powered by Claude, with four specialised agents handling profiling, validation, repair, and reporting in sequence.

## Problem Statement

Raw data is rarely clean. Missing values, inconsistent formatting, duplicate records, and out-of-range values are endemic to real-world datasets, and no single fix works for all of them. A single model cannot reliably handle all of this in one pass. Breaking the problem into discrete agents, each with a specific role and a typed contract with the next, keeps failures catchable and the output trustworthy.

## How it works

Four agents run in sequence, each handing its output to the next.

**Profiler** reads the dataset and figures out what each column actually is: an age, an email, a currency amount, a category, etc. Missing value patterns are analysed statistically to understand whether gaps are random or systematic.

**Validator** looks at what the profiler found and decides what rules apply to each column. An age column gets range checks, an email column gets format checks, and so on. Nothing is hardcoded; it adapts to whatever columns are present.

**Repairer** fixes what it can: duplicates, formatting inconsistencies, out-of-range values, missing entries. Columns where the missing data is non-random are left alone, since filling them in would silently skew the data.

**Reporter** writes up everything that was found and fixed into a structured markdown report.

## Results

On the included synthetic Human Resources dataset (520 rows, 9 columns):

| Metric | Before | After |
|---|---|---|
| Row Count | 520 | 441 |
| Null Count | 84 | 0 |
| Duplicate Rows | 20 | 0 |

10 repair actions were applied across 7 columns: duplicate removal, row drops for invalid emails, out-of-range age nullification with median imputation, currency symbol stripping, date format standardization, and categorical case normalization. See `docs/data_quality_report.md` for the full report from the last run.

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

A synthetic HR dataset is included at `data/raw/messy_data.csv` as a test fixture. Run `make run` after setup to confirm everything is working before trying your own data.

```bash
uv sync
make run     # Run the pipeline on the included sample dataset
make serve   # Start the web interface without Docker
make test    # Run the test suite
```

To run on your own CSV:

```bash
uv run python -m src.data_quality_pipeline.pipeline path/to/your/data.csv
```

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
│       ├── jobs.py
│       ├── models.py
│       ├── pipeline.py
│       ├── server.py
│       └── tools.py
├── static/
│   └── index.html
├── tests/
│   ├── conftest.py
│   ├── test_profiler.py
│   ├── test_tools.py
│   └── test_validator.py
├── .env.example
├── .python-version
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pyproject.toml
└── uv.lock
```
