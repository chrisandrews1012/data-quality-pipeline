"""
Deterministic invariant checks that verify LLM outputs against ground truth.

Each function returns a list of violation strings. An empty list means all
checks passed. Call assert_invariants() to raise on failure.

These catch hallucination: the LLM may claim row counts, null counts, or
column names that don't match the actual data. Pydantic guarantees structural
validity; these checks guarantee factual accuracy.
"""

import pandas as pd

from .models import DataProfile, RepairReport, ValidationReport

# Tolerance for floating-point comparisons (percentage points).
# The LLM receives pre-computed stats and is expected to reproduce them faithfully,
# but may round slightly differently. 0.5 pp catches real hallucinations while
# absorbing rounding noise.
_PCT_TOLERANCE = 0.5


class InvariantViolation(Exception):
    pass


def check_profile_invariants(profile: DataProfile, df: pd.DataFrame) -> list[str]:
    """
    Verify that DataProfile numeric facts match the raw DataFrame.

    Checks dataset-level counts, per-column null/unique counts, and that
    every profiled column actually exists in the CSV (and vice versa).

    :param profile: DataProfile returned by the Profiler agent.
    :param df: The raw DataFrame that was profiled.
    :returns: List of violation strings. Empty means all checks passed.
    """
    violations: list[str] = []

    actual_rows = len(df)
    actual_cols = len(df.columns)
    actual_nulls = int(df.isnull().sum().sum())
    actual_dupes = int(df.duplicated().sum())

    if profile.row_count != actual_rows:
        violations.append(
            f"row_count claimed {profile.row_count}, actual {actual_rows}"
        )
    if profile.column_count != actual_cols:
        violations.append(
            f"column_count claimed {profile.column_count}, actual {actual_cols}"
        )
    if profile.total_null_count != actual_nulls:
        violations.append(
            f"total_null_count claimed {profile.total_null_count}, actual {actual_nulls}"
        )
    if profile.duplicate_row_count != actual_dupes:
        violations.append(
            f"duplicate_row_count claimed {profile.duplicate_row_count}, actual {actual_dupes}"
        )

    df_col_set = set(df.columns)
    profiled_col_set = {cp.name for cp in profile.columns}

    for cp in profile.columns:
        if cp.name not in df_col_set:
            violations.append(f"Profiled column '{cp.name}' does not exist in CSV")
            continue

        actual_null_count = int(df[cp.name].isnull().sum())
        if cp.null_count != actual_null_count:
            violations.append(
                f"'{cp.name}': null_count claimed {cp.null_count}, actual {actual_null_count}"
            )

        actual_null_pct = round(df[cp.name].isnull().mean() * 100, 2)
        if abs(cp.null_pct - actual_null_pct) > _PCT_TOLERANCE:
            violations.append(
                f"'{cp.name}': null_pct claimed {cp.null_pct}, actual {actual_null_pct}"
            )

        actual_unique = int(df[cp.name].nunique())
        if cp.unique_count != actual_unique:
            violations.append(
                f"'{cp.name}': unique_count claimed {cp.unique_count}, actual {actual_unique}"
            )

    for col in df.columns:
        if col not in profiled_col_set:
            violations.append(f"Column '{col}' in CSV was not profiled")

    return violations


def check_validation_invariants(
    validation: ValidationReport, profile: DataProfile
) -> list[str]:
    """
    Verify internal consistency of a ValidationReport.

    Checks that failure_count matches len(failures), that passed reflects
    the actual presence of critical failures, and that every referenced
    column exists in the profile.

    :param validation: ValidationReport returned by the Validator agent.
    :param profile: The DataProfile the validator was given.
    :returns: List of violation strings. Empty means all checks passed.
    """
    violations: list[str] = []

    if validation.failure_count != len(validation.failures):
        violations.append(
            f"failure_count={validation.failure_count} but len(failures)={len(validation.failures)}"
        )

    critical_count = sum(1 for f in validation.failures if f.severity == "critical")
    if critical_count > 0 and validation.passed:
        violations.append(
            f"passed=True but {critical_count} critical failure(s) exist"
        )
    if critical_count == 0 and not validation.passed:
        violations.append("passed=False but no critical failures were found")

    # "(all columns)" is the only permitted dataset-level label. The validator
    # system prompt instructs the model to use this exact string.
    known_cols = {cp.name for cp in profile.columns} | {"(all columns)"}

    for failure in validation.failures:
        if failure.column not in known_cols:
            violations.append(
                f"ValidationFailure references unknown column '{failure.column}'"
            )

    for rule in validation.rules_applied:
        if rule.column not in known_cols:
            violations.append(
                f"ValidationRule references unknown column '{rule.column}'"
            )

    return violations


def check_repair_invariants(
    repair: RepairReport,
    input_df: pd.DataFrame,
    output_df: pd.DataFrame,
) -> list[str]:
    """
    Verify RepairReport facts against the actual before/after DataFrames.

    Checks total_repairs count, rows_dropped against the actual row delta,
    and that every RepairAction column exists in the input data.

    :param repair: RepairReport returned by the Repairer agent.
    :param input_df: The raw DataFrame before repairs.
    :param output_df: The cleaned DataFrame after repairs.
    :returns: List of violation strings. Empty means all checks passed.
    """
    violations: list[str] = []

    if repair.total_repairs != len(repair.actions):
        violations.append(
            f"total_repairs={repair.total_repairs} but len(actions)={len(repair.actions)}"
        )

    actual_delta = len(input_df) - len(output_df)
    if repair.rows_dropped != actual_delta:
        violations.append(
            f"rows_dropped claimed {repair.rows_dropped}, actual row delta is {actual_delta}"
        )

    if repair.rows_dropped > len(input_df):
        violations.append(
            f"rows_dropped={repair.rows_dropped} exceeds input row count {len(input_df)}"
        )

    known_cols = set(input_df.columns) | {"(all columns)"}
    for action in repair.actions:
        if action.column not in known_cols:
            violations.append(
                f"RepairAction references unknown column '{action.column}'"
            )

    return violations


def assert_invariants(violations: list[str], agent_name: str) -> None:
    """
    Raise InvariantViolation if any violations were found.

    :param violations: List returned by a check_*_invariants function.
    :param agent_name: Label used in the error message (e.g. "Profiler").
    :raises InvariantViolation: If violations is non-empty.
    """
    if violations:
        bullet_list = "\n".join(f"  - {v}" for v in violations)
        raise InvariantViolation(
            f"{agent_name} invariant violations detected:\n{bullet_list}"
        )
