"""
Fast deterministic tests for apply_repairs().

The LLM part of the repairer (producing the RepairReport narrative) is not
tested here. These tests cover only the Python repair logic, which is
deterministic and does not require an API call.
"""

import pandas as pd
import pytest

from src.data_quality_pipeline.agents.repairer import apply_repairs
from src.data_quality_pipeline.models import (
    ColumnMissingness,
    ColumnProfile,
    DataProfile,
    MissingnessReport,
)


def make_profile(columns: list[tuple[str, str]], missingness: list[tuple[str, str, bool]] | None = None) -> DataProfile:
    """Helper: build a minimal DataProfile from (name, inferred_type) pairs."""
    col_profiles = [
        ColumnProfile(
            name=name,
            dtype="object",
            null_count=0,
            null_pct=0.0,
            unique_count=1,
            unique_pct=100.0,
            sample_values=[],
            inferred_type=itype,
        )
        for name, itype in columns
    ]
    miss_report = None
    if missingness:
        miss_report = MissingnessReport(
            dataset_mcar_conclusion="test",
            columns_analyzed=[
                ColumnMissingness(
                    column=col,
                    null_count=1,
                    null_pct=5.0,
                    mechanism=mechanism,
                    confidence="medium",
                    evidence="test",
                    correlated_with=[],
                    safe_to_impute=safe,
                )
                for col, mechanism, safe in missingness
            ],
            summary="test",
        )
    return DataProfile(
        dataset_name="test",
        row_count=1,
        column_count=len(columns),
        duplicate_row_count=0,
        total_null_count=0,
        columns=col_profiles,
        summary="test",
        missingness=miss_report,
    )


# Duplicate removal
def test_apply_repairs_removes_duplicates():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    profile = make_profile([("a", "numeric"), ("b", "categorical")])
    cleaned, actions, rows_dropped, _ = apply_repairs(df, profile)
    assert len(cleaned) == 2
    assert rows_dropped == 1
    assert any("duplicate" in a.issue.lower() for a in actions)


def test_apply_repairs_no_duplicates_no_action():
    df = pd.DataFrame({"a": [1, 2, 3]})
    profile = make_profile([("a", "numeric")])
    _, actions, rows_dropped, _ = apply_repairs(df, profile)
    assert rows_dropped == 0
    assert not any("duplicate" in a.issue.lower() for a in actions)


# Currency cleaning
def test_apply_repairs_strips_currency_symbols():
    df = pd.DataFrame({"salary": ["$50,000.00", "60000", "$75,000.00"]})
    profile = make_profile([("salary", "currency")])
    cleaned, actions, _, _ = apply_repairs(df, profile)
    assert cleaned["salary"].iloc[0] == 50000.0
    assert any(a.column == "salary" and a.action_taken == "reformatted" for a in actions)


def test_apply_repairs_imputes_null_currency():
    df = pd.DataFrame({"salary": [50000.0, None, 60000.0]})
    profile = make_profile([("salary", "currency")])
    cleaned, actions, _, _ = apply_repairs(df, profile)
    assert cleaned["salary"].isnull().sum() == 0
    assert any(a.column == "salary" and a.action_taken == "imputed_median" for a in actions)


# Age out-of-range
def test_apply_repairs_nullifies_out_of_range_age():
    df = pd.DataFrame({"age": [25.0, 150.0, -5.0, 40.0]})
    profile = make_profile([("age", "age")])
    cleaned, actions, _, _ = apply_repairs(df, profile)
    flagged = [a for a in actions if a.column == "age" and a.action_taken == "flagged"]
    assert len(flagged) == 1
    assert flagged[0].rows_affected == 2


def test_apply_repairs_imputes_null_age_after_out_of_range():
    df = pd.DataFrame({"age": [25.0, 150.0, 30.0, 35.0]})
    profile = make_profile([("age", "age")])
    cleaned, actions, _, _ = apply_repairs(df, profile)
    assert cleaned["age"].isnull().sum() == 0
    assert any(a.column == "age" and a.action_taken == "imputed_median" for a in actions)


def test_apply_repairs_no_age_action_on_valid_data():
    df = pd.DataFrame({"age": [25.0, 30.0, 45.0]})
    profile = make_profile([("age", "age")])
    _, actions, _, _ = apply_repairs(df, profile)
    assert not any(a.column == "age" for a in actions)


# Date standardization
def test_apply_repairs_standardizes_dates():
    df = pd.DataFrame({"hire_date": ["2023-01-15", "01/15/2023", "January 15, 2023"]})
    profile = make_profile([("hire_date", "date")])
    cleaned, actions, _, _ = apply_repairs(df, profile)
    assert all(cleaned["hire_date"].str.match(r"^\d{4}-\d{2}-\d{2}$"))
    assert any(a.column == "hire_date" and a.action_taken == "reformatted" for a in actions)


def test_apply_repairs_no_date_action_on_standard_dates():
    df = pd.DataFrame({"hire_date": ["2023-01-15", "2023-06-20"]})
    profile = make_profile([("hire_date", "date")])
    _, actions, _, _ = apply_repairs(df, profile)
    assert not any(a.column == "hire_date" for a in actions)


# Categorical case normalization
def test_apply_repairs_normalizes_categorical_case():
    df = pd.DataFrame({"dept": ["engineering", "Marketing", "SALES"]})
    profile = make_profile([("dept", "categorical")])
    cleaned, actions, _, _ = apply_repairs(df, profile)
    assert cleaned["dept"].iloc[0] == "Engineering"
    assert any(a.column == "dept" and a.action_taken == "reformatted" for a in actions)


def test_apply_repairs_imputes_null_categorical():
    df = pd.DataFrame({"dept": ["Engineering", None, "Engineering"]})
    profile = make_profile([("dept", "categorical")])
    cleaned, actions, _, _ = apply_repairs(df, profile)
    assert cleaned["dept"].isnull().sum() == 0
    assert any(a.column == "dept" and a.action_taken == "imputed_mode" for a in actions)


# MNAR columns are skipped
def test_apply_repairs_skips_mnar_column():
    # id column makes each row unique so drop_duplicates doesn't collapse nulls
    df = pd.DataFrame({"id": [1, 2, 3, 4, 5], "score": [1.0, None, 3.0, None, 5.0]})
    profile = make_profile(
        [("id", "id"), ("score", "numeric")],
        missingness=[("score", "MNAR", False)],
    )
    cleaned, actions, _, unresolved = apply_repairs(df, profile)
    assert not any(a.column == "score" for a in actions)
    assert any("score" in u and "MNAR" in u for u in unresolved)
    assert cleaned["score"].isnull().sum() == 2  # nulls untouched


# Sparse columns are escalated to unresolved
def test_apply_repairs_escalates_sparse_column():
    # Unique record_id ensures null rows aren't identical to each other,
    # so drop_duplicates leaves the null rate above the 50% sparse threshold.
    ids = [f"id_{i}" for i in range(100)]
    notes = [None] * 60 + [f"note {i}" for i in range(40)]
    df = pd.DataFrame({"record_id": ids, "notes": notes})
    profile = make_profile([("record_id", "id"), ("notes", "text")])
    _, actions, _, unresolved = apply_repairs(df, profile)
    assert not any(a.column == "notes" for a in actions)
    assert any("notes" in u for u in unresolved)


# Email issues go to unresolved
def test_apply_repairs_puts_invalid_emails_in_unresolved():
    df = pd.DataFrame({"email": ["good@example.com", "notanemail", "also-bad"]})
    profile = make_profile([("email", "email")])
    _, actions, _, unresolved = apply_repairs(df, profile)
    assert not any(a.column == "email" for a in actions)
    assert any("email" in u.lower() for u in unresolved)


# ID nulls go to unresolved
def test_apply_repairs_puts_null_ids_in_unresolved():
    df = pd.DataFrame({"user_id": ["abc", None, "def"]})
    profile = make_profile([("user_id", "id")])
    _, actions, _, unresolved = apply_repairs(df, profile)
    assert not any(a.column == "user_id" for a in actions)
    assert any("user_id" in u for u in unresolved)
