import pandas as pd
import pytest

from src.data_quality_pipeline.agents.profiler import run_profiler
from src.data_quality_pipeline.models import DataProfile

pytestmark = pytest.mark.llm


@pytest.fixture
def sample_csv(tmp_path):
    df = pd.DataFrame({
        "user_id": ["a", "b", "c", "d"],
        "email": ["user@test.com", "bad-email", None, "another@test.com"],
        "age": [25, 300, None, 45],
        "salary": ["$50,000", "60000", "70000", "80000"],
        "department": ["engineering", "Marketing", "Sales", "hr"],
    })
    path = tmp_path / "test.csv"
    df.to_csv(path, index=False)
    return str(path)


def test_profiler_returns_dataprofile(sample_csv):
    profile = run_profiler(sample_csv)
    assert isinstance(profile, DataProfile)


def test_profiler_row_count(sample_csv):
    profile = run_profiler(sample_csv)
    assert profile.row_count == 4


def test_profiler_column_count(sample_csv):
    profile = run_profiler(sample_csv)
    assert profile.column_count == 5


def test_profiler_detects_nulls(sample_csv):
    profile = run_profiler(sample_csv)
    email_col = next(c for c in profile.columns if c.name == "email")
    assert email_col.null_count == 1


def test_profiler_infers_types(sample_csv):
    profile = run_profiler(sample_csv)
    col_types = {c.name: c.inferred_type for c in profile.columns}
    assert col_types["email"] == "email"
    assert col_types["age"] == "age"
    assert col_types["department"] == "categorical"


def test_profiler_attaches_missingness(sample_csv):
    profile = run_profiler(sample_csv)
    assert profile.missingness is not None
    assert isinstance(profile.missingness.summary, str)
    assert len(profile.missingness.columns_analyzed) > 0


def test_profiler_missingness_columns_have_mechanism(sample_csv):
    profile = run_profiler(sample_csv)
    for cm in profile.missingness.columns_analyzed:
        assert cm.mechanism in ("MCAR", "MAR", "MNAR", "none")
        assert isinstance(cm.safe_to_impute, bool)
