.PHONY: install data run serve test clean all

install:
	uv sync

data:
	uv run python data/generate_hr.py
	uv run python data/generate_hr_clean.py
	uv run python data/generate_ecommerce.py
	uv run python data/generate_medical.py

run:
	uv run python -m src.data_quality_pipeline.pipeline

serve:
	uv run uvicorn src.data_quality_pipeline.server:app --reload

test:
	uv run pytest tests/ -v

test-fast:
	uv run pytest tests/ -m "not llm" -v

test-llm:
	uv run pytest tests/ -m llm -v

eval:
	uv run python evals/runner.py

clean:
	rm -f data/processed/cleaned_data.csv
	rm -f docs/data_quality_report.md
	rm -rf evals/results/

all: install data run
