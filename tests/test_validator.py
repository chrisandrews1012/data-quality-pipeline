import pytest

from src.data_quality_pipeline.agents.validator import run_validator
from src.data_quality_pipeline.models import (
    ColumnMissingness,
    ColumnProfile,
    DataProfile,
    MissingnessReport,
    ValidationReport,
)


def make_profile() -> DataProfile:
    return DataProfile(
        dataset_name="test",
        row_count=100,
        column_count=3,
        duplicate_row_count=5,
        total_null_count=15,
        columns=[
            ColumnProfile(
                name="user_id",
                dtype="object",
                null_count=0,
                null_pct=0.0,
                unique_count=100,
                unique_pct=100.0,
                sample_values=["abc123", "def456"],
                inferred_type="id",
            ),
            ColumnProfile(
                name="email",
                dtype="object",
                null_count=10,
                null_pct=10.0,
                unique_count=90,
                unique_pct=90.0,
                sample_values=["notanemail", "also-bad", "good@test.com"],
                inferred_type="email",
            ),
            ColumnProfile(
                name="age",
                dtype="float64",
                null_count=5,
                null_pct=5.0,
                unique_count=50,
                unique_pct=50.0,
                sample_values=["150", "-5", "25"],
                min_value="-5",
                max_value="150",
                mean_value=45.0,
                inferred_type="age",
            ),
        ],
        summary="Test profile with known issues.",
        missingness=MissingnessReport(
            dataset_mcar_conclusion="not MCAR (p=0.01): missingness is likely MAR or MNAR",
            dataset_mcar_pvalue=0.01,
            columns_analyzed=[
                ColumnMissingness(
                    column="email",
                    null_count=10,
                    null_pct=10.0,
                    mechanism="MAR",
                    confidence="medium",
                    evidence="Correlated with age.",
                    correlated_with=["age"],
                    safe_to_impute=True,
                ),
                ColumnMissingness(
                    column="age",
                    null_count=5,
                    null_pct=5.0,
                    mechanism="MCAR",
                    confidence="medium",
                    evidence="Low null rate, no correlation.",
                    correlated_with=[],
                    safe_to_impute=True,
                ),
            ],
            summary="1 MAR column, 1 MCAR column.",
        ),
    )


def test_validator_returns_report():
    report = run_validator(make_profile())
    assert isinstance(report, ValidationReport)


def test_validator_applies_rules():
    report = run_validator(make_profile())
    assert len(report.rules_applied) > 0


def test_validator_flags_bad_email():
    report = run_validator(make_profile())
    email_failures = [f for f in report.failures if f.column == "email"]
    assert len(email_failures) > 0


def test_validator_flags_bad_age():
    report = run_validator(make_profile())
    age_failures = [f for f in report.failures if f.column == "age"]
    assert len(age_failures) > 0


def test_validator_flags_duplicates():
    report = run_validator(make_profile())
    dup_failures = [f for f in report.failures if "duplicate" in f.rule.lower()]
    assert len(dup_failures) > 0


def test_validator_passed_field_reflects_critical_failures():
    report = run_validator(make_profile())
    critical = [f for f in report.failures if f.severity == "critical"]
    if critical:
        assert report.passed is False
    else:
        assert report.passed is True
