.PHONY: install data run serve test clean all

install:
	uv sync

data:
	uv run python data/generate_synthetic.py

run:
	uv run python -m src.data_quality_pipeline.pipeline

serve:
	uv run uvicorn src.data_quality_pipeline.server:app --reload

test:
	uv run pytest tests/ -v

test-fast:
	uv run pytest tests/test_tools.py -v

clean:
	rm -f data/raw/messy_data.csv
	rm -f data/processed/cleaned_data.csv
	rm -f docs/data_quality_report.md

all: install data run
