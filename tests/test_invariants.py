"""
Fast deterministic tests for invariant checks.

These tests never call the LLM. They construct known-good and known-bad
inputs, then verify the invariant functions catch violations correctly.
"""

import pandas as pd
import pytest

from src.data_quality_pipeline.invariants import (
    InvariantViolation,
    assert_invariants,
    check_profile_invariants,
    check_repair_invariants,
    check_validation_invariants,
)
from src.data_quality_pipeline.models import (
    ColumnMissingness,
    ColumnProfile,
    DataProfile,
    MissingnessReport,
    RepairAction,
    RepairReport,
    ValidationFailure,
    ValidationReport,
    ValidationRule,
)


# Fixtures
@pytest.fixture
def simple_df():
    return pd.DataFrame({
        "id": ["a", "b", "c"],
        "email": ["x@y.com", None, "z@w.com"],
        "age": [25, 30, 45],
    })


def make_correct_profile(df: pd.DataFrame) -> DataProfile:
    return DataProfile(
        dataset_name="test",
        row_count=len(df),
        column_count=len(df.columns),
        duplicate_row_count=int(df.duplicated().sum()),
        total_null_count=int(df.isnull().sum().sum()),
        columns=[
            ColumnProfile(
                name="id",
                dtype="object",
                null_count=int(df["id"].isnull().sum()),
                null_pct=round(df["id"].isnull().mean() * 100, 2),
                unique_count=int(df["id"].nunique()),
                unique_pct=round(df["id"].nunique() / len(df) * 100, 2),
                sample_values=["a", "b"],
                inferred_type="id",
            ),
            ColumnProfile(
                name="email",
                dtype="object",
                null_count=int(df["email"].isnull().sum()),
                null_pct=round(df["email"].isnull().mean() * 100, 2),
                unique_count=int(df["email"].nunique()),
                unique_pct=round(df["email"].nunique() / len(df) * 100, 2),
                sample_values=["x@y.com"],
                inferred_type="email",
            ),
            ColumnProfile(
                name="age",
                dtype="int64",
                null_count=int(df["age"].isnull().sum()),
                null_pct=round(df["age"].isnull().mean() * 100, 2),
                unique_count=int(df["age"].nunique()),
                unique_pct=round(df["age"].nunique() / len(df) * 100, 2),
                sample_values=["25", "30"],
                inferred_type="age",
            ),
        ],
        summary="Test profile.",
    )


# check_profile_invariants
def test_profile_invariants_pass_on_correct_output(simple_df):
    profile = make_correct_profile(simple_df)
    assert check_profile_invariants(profile, simple_df) == []


def test_profile_invariants_catches_wrong_row_count(simple_df):
    profile = make_correct_profile(simple_df)
    profile.row_count = 99
    violations = check_profile_invariants(profile, simple_df)
    assert any("row_count" in v for v in violations)


def test_profile_invariants_catches_wrong_null_count(simple_df):
    profile = make_correct_profile(simple_df)
    profile.total_null_count = 0  # actual is 1
    violations = check_profile_invariants(profile, simple_df)
    assert any("total_null_count" in v for v in violations)


def test_profile_invariants_catches_wrong_duplicate_count(simple_df):
    df = pd.DataFrame({"a": [1, 1, 2], "b": [1, 1, 2]})
    profile = make_correct_profile(simple_df)  # wrong df stats
    profile.duplicate_row_count = 0
    violations = check_profile_invariants(profile, df)
    assert any("duplicate_row_count" in v for v in violations)


def test_profile_invariants_catches_invented_column(simple_df):
    profile = make_correct_profile(simple_df)
    profile.columns[0].name = "nonexistent_col"
    violations = check_profile_invariants(profile, simple_df)
    assert any("nonexistent_col" in v for v in violations)


def test_profile_invariants_catches_missing_column(simple_df):
    profile = make_correct_profile(simple_df)
    profile.columns = profile.columns[:2]  # drop age
    violations = check_profile_invariants(profile, simple_df)
    assert any("age" in v for v in violations)


def test_profile_invariants_catches_wrong_per_column_null_count(simple_df):
    profile = make_correct_profile(simple_df)
    email_col = next(c for c in profile.columns if c.name == "email")
    email_col.null_count = 0  # actual is 1
    violations = check_profile_invariants(profile, simple_df)
    assert any("email" in v and "null_count" in v for v in violations)


def test_profile_invariants_catches_wrong_unique_count(simple_df):
    profile = make_correct_profile(simple_df)
    age_col = next(c for c in profile.columns if c.name == "age")
    age_col.unique_count = 1  # actual is 3
    violations = check_profile_invariants(profile, simple_df)
    assert any("age" in v and "unique_count" in v for v in violations)


# check_validation_invariants
def make_passing_validation(profile: DataProfile) -> ValidationReport:
    return ValidationReport(
        passed=True,
        rules_applied=[
            ValidationRule(column="email", rule_description="email format", severity="critical"),
        ],
        failure_count=0,
        failures=[],
        summary="No issues.",
    )


def test_validation_invariants_pass_on_consistent_output(simple_df):
    profile = make_correct_profile(simple_df)
    report = make_passing_validation(profile)
    assert check_validation_invariants(report, profile) == []


def test_validation_invariants_catches_failure_count_mismatch(simple_df):
    profile = make_correct_profile(simple_df)
    report = make_passing_validation(profile)
    report.failure_count = 5  # but failures is []
    violations = check_validation_invariants(report, profile)
    assert any("failure_count" in v for v in violations)


def test_validation_invariants_catches_passed_true_with_critical_failure(simple_df):
    profile = make_correct_profile(simple_df)
    report = ValidationReport(
        passed=True,
        rules_applied=[ValidationRule(column="email", rule_description="email format", severity="critical")],
        failure_count=1,
        failures=[
            ValidationFailure(
                column="email",
                rule="email format check",
                severity="critical",
                affected_rows=5,
                description="Invalid emails found",
                suggested_fix="Drop or correct rows",
            )
        ],
        summary="Issues found.",
    )
    violations = check_validation_invariants(report, profile)
    assert any("passed=True" in v for v in violations)


def test_validation_invariants_catches_passed_false_no_critical(simple_df):
    profile = make_correct_profile(simple_df)
    report = ValidationReport(
        passed=False,
        rules_applied=[ValidationRule(column="email", rule_description="email format", severity="info")],
        failure_count=1,
        failures=[
            ValidationFailure(
                column="email",
                rule="email format check",
                severity="info",
                affected_rows=1,
                description="Minor issue",
                suggested_fix="Review",
            )
        ],
        summary="Issues found.",
    )
    violations = check_validation_invariants(report, profile)
    assert any("passed=False" in v for v in violations)


def test_validation_invariants_catches_invented_column(simple_df):
    profile = make_correct_profile(simple_df)
    report = make_passing_validation(profile)
    report.failures = [
        ValidationFailure(
            column="nonexistent",
            rule="some rule",
            severity="critical",
            affected_rows=1,
            description="Invented issue",
            suggested_fix="N/A",
        )
    ]
    report.failure_count = 1
    report.passed = False
    violations = check_validation_invariants(report, profile)
    assert any("nonexistent" in v for v in violations)


def test_validation_invariants_allows_all_columns_label(simple_df):
    # "(all columns)" is the required label for dataset-level rules like duplicates.
    profile = make_correct_profile(simple_df)
    report = ValidationReport(
        passed=False,
        rules_applied=[ValidationRule(column="(all columns)", rule_description="duplicate check", severity="critical")],
        failure_count=1,
        failures=[
            ValidationFailure(
                column="(all columns)",
                rule="duplicate rows",
                severity="critical",
                affected_rows=2,
                description="Duplicates found",
                suggested_fix="Remove duplicates",
            )
        ],
        summary="Issues found.",
    )
    assert check_validation_invariants(report, profile) == []


def test_validation_invariants_rejects_nonstandard_dataset_labels(simple_df):
    # Labels like "[dataset]" and "_dataset_" are not permitted. The validator
    # prompt requires "(all columns)" for dataset-level rules.
    profile = make_correct_profile(simple_df)
    for bad_label in ["[dataset]", "_dataset_", "(dataset)"]:
        report = ValidationReport(
            passed=False,
            rules_applied=[ValidationRule(column=bad_label, rule_description="duplicate check", severity="critical")],
            failure_count=1,
            failures=[
                ValidationFailure(
                    column=bad_label,
                    rule="duplicate rows",
                    severity="critical",
                    affected_rows=2,
                    description="Duplicates found",
                    suggested_fix="Remove duplicates",
                )
            ],
            summary="Issues found.",
        )
        violations = check_validation_invariants(report, profile)
        assert any(bad_label in v for v in violations), f"Bad label '{bad_label}' was not caught"


# check_repair_invariants
def make_repair_report(rows_dropped: int, actions: list) -> RepairReport:
    return RepairReport(
        total_repairs=len(actions),
        rows_dropped=rows_dropped,
        actions=actions,
        unresolved=[],
        output_path="/tmp/cleaned.csv",
        summary="Repairs done.",
    )


def test_repair_invariants_pass_on_correct_output(simple_df):
    output_df = simple_df.copy()
    report = make_repair_report(0, [])
    assert check_repair_invariants(report, simple_df, output_df) == []


def test_repair_invariants_catches_wrong_rows_dropped():
    input_df = pd.DataFrame({"a": [1, 2, 3, 4, 5]})
    output_df = pd.DataFrame({"a": [1, 2, 3]})  # 2 rows dropped
    report = make_repair_report(rows_dropped=0, actions=[])  # claims 0
    violations = check_repair_invariants(report, input_df, output_df)
    assert any("rows_dropped" in v for v in violations)


def test_repair_invariants_catches_total_repairs_mismatch(simple_df):
    output_df = simple_df.copy()
    report = make_repair_report(0, [])
    report.total_repairs = 5  # mismatch with len([])
    violations = check_repair_invariants(report, simple_df, output_df)
    assert any("total_repairs" in v for v in violations)


def test_repair_invariants_catches_invented_column(simple_df):
    output_df = simple_df.copy()
    action = RepairAction(
        column="phantom_col",
        issue="Something",
        action_taken="reformatted",
        rows_affected=1,
        before_example="x",
        after_example="y",
        reason="test",
    )
    report = make_repair_report(0, [action])
    violations = check_repair_invariants(report, simple_df, output_df)
    assert any("phantom_col" in v for v in violations)


def test_repair_all_columns_label_is_allowed(simple_df):
    output_df = simple_df.iloc[:2].copy()  # 1 row dropped
    action = RepairAction(
        column="(all columns)",
        issue="Duplicate rows",
        action_taken="dropped_rows",
        rows_affected=1,
        before_example="duplicate row",
        after_example="removed",
        reason="Duplicates skew aggregations.",
    )
    report = make_repair_report(1, [action])
    assert check_repair_invariants(report, simple_df, output_df) == []


# assert_invariants
def test_assert_invariants_raises_on_violations():
    with pytest.raises(InvariantViolation, match="Profiler"):
        assert_invariants(["row_count claimed 99, actual 3"], "Profiler")


def test_assert_invariants_silent_on_empty():
    assert_invariants([], "Profiler") is None
