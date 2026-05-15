import numpy as np
import pandas as pd
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel

from ..models import DataProfile, RepairAction, RepairReport
from ..tools import (
    clean_numeric_string,
    count_non_standard_dates,
    detect_case_inconsistency,
    is_valid_email,
    load_dataframe,
    save_dataframe,
    standardize_case,
    standardize_date,
)

model = AnthropicModel("claude-sonnet-4-6")

repairer_agent = Agent(
    model=model,
    output_type=RepairReport,
    system_prompt="""
    You are a data repair agent. You receive a summary of repairs that were
    applied to a dataset and produce a structured RepairReport documenting them.

    Only document repairs that were actually performed.
    For each action include a clear reason explaining why that action was
    chosen over alternatives (e.g. why median imputation over mean, why
    dropping rows over flagging).

    List any issues that could not be automatically resolved in the
    unresolved field with a plain English explanation.
    """,
)

# Columns with more than 50% nulls are too sparse to auto-repair.
SPARSE_THRESHOLD = 0.5


def apply_repairs(
    df: pd.DataFrame,
    profile: DataProfile,
) -> tuple[pd.DataFrame, list[RepairAction], int, list[str]]:
    """
    Apply repairs to the DataFrame driven by each column's inferred semantic type.

    MNAR columns are always skipped regardless of null rate, since imputation
    would introduce systematic bias. Columns above SPARSE_THRESHOLD are also
    skipped. All other columns are repaired according to their inferred type.

    :param df: The raw input DataFrame.
    :type df: pd.DataFrame
    :param profile: DataProfile from the Profiler agent, including missingness analysis.
    :type profile: DataProfile
    :returns: Tuple of (cleaned DataFrame, repair actions, rows dropped, unresolved issues).
    :rtype: tuple[pd.DataFrame, list[RepairAction], int, list[str]]
    """
    actions: list[RepairAction] = []
    rows_dropped = 0
    unresolved: list[str] = []

    col_types = {cp.name: cp.inferred_type for cp in profile.columns}

    # Build a lookup of safe_to_impute from the missingness analysis.
    # MNAR columns have safe_to_impute=False and must not be imputed.
    miss_lookup: dict[str, bool] = {}
    if profile.missingness:
        miss_lookup = {
            cm.column: cm.safe_to_impute
            for cm in profile.missingness.columns_analyzed
        }

    # Duplicates 
    before = len(df)
    df = df.drop_duplicates()
    dropped = before - len(df)
    if dropped > 0:
        actions.append(RepairAction(
            column="(all columns)",
            issue="Duplicate rows",
            action_taken="dropped_rows",
            rows_affected=dropped,
            before_example="Identical row appearing multiple times",
            after_example="One copy retained, duplicates removed",
            reason="Duplicate rows inflate counts and skew aggregations.",
        ))
        rows_dropped += dropped

    # Per-column repairs 
    for col in df.columns:
        inferred = col_types.get(col, "unknown")
        null_pct = df[col].isnull().mean()

        if null_pct > SPARSE_THRESHOLD:
            unresolved.append(
                f"'{col}' ({inferred}): {null_pct:.0%} null. Too sparse to "
                f"auto-repair. Manual review recommended."
            )
            continue

        # MNAR columns must not be imputed regardless of null rate.
        if not miss_lookup.get(col, True):
            cm = next(
                (c for c in profile.missingness.columns_analyzed if c.column == col),
                None,
            )
            mechanism = cm.mechanism if cm else "MNAR"
            unresolved.append(
                f"'{col}' ({inferred}): classified as {mechanism}. "
                f"Imputation would bias results. Manual review required."
            )
            continue

        # currency 
        if inferred == "currency":
            bad_mask = df[col].apply(
                lambda x: isinstance(x, str) and any(c in str(x) for c in ["$", "£", "€", ","])
            )
            bad_count = int(bad_mask.sum())
            if bad_count > 0:
                example_before = df.loc[bad_mask, col].iloc[0]
                df[col] = df[col].apply(clean_numeric_string)
                actions.append(RepairAction(
                    column=col,
                    issue="Currency symbols or commas in numeric field",
                    action_taken="reformatted",
                    rows_affected=bad_count,
                    before_example=str(example_before),
                    after_example=str(clean_numeric_string(example_before)),
                    reason="Stripping symbols makes the column numeric and usable in calculations.",
                ))
            null_count = int(df[col].isnull().sum())
            if null_count > 0:
                df[col] = pd.to_numeric(df[col], errors="coerce")
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
                actions.append(RepairAction(
                    column=col,
                    issue="Null values in currency column",
                    action_taken="imputed_median",
                    rows_affected=null_count,
                    before_example="NaN",
                    after_example=str(round(median_val, 2)),
                    reason="Median is robust to outliers, better than mean for skewed financial data.",
                ))

        # age 
        elif inferred == "age":
            df[col] = pd.to_numeric(df[col], errors="coerce")
            bad_age = (df[col] < 0) | (df[col] > 120)
            bad_count = int(bad_age.sum())
            if bad_count > 0:
                example_before = df.loc[bad_age, col].iloc[0]
                df.loc[bad_age, col] = np.nan
                actions.append(RepairAction(
                    column=col,
                    issue="Out-of-range age values (< 0 or > 120)",
                    action_taken="flagged",
                    rows_affected=bad_count,
                    before_example=str(example_before),
                    after_example="Set to NaN for imputation",
                    reason="Values outside 0-120 are biologically impossible and likely data entry errors.",
                ))
            null_count = int(df[col].isnull().sum())
            if null_count > 0:
                median_age = df[col].median()
                df[col] = df[col].fillna(median_age)
                actions.append(RepairAction(
                    column=col,
                    issue="Null age values",
                    action_taken="imputed_median",
                    rows_affected=null_count,
                    before_example="NaN",
                    after_example=str(round(median_age, 1)),
                    reason="Median age preserves distribution better than mean when outliers exist.",
                ))

        # email 
        elif inferred == "email":
            null_count = int(df[col].isnull().sum())
            if null_count > 0:
                df = df.dropna(subset=[col])
                rows_dropped += null_count
                actions.append(RepairAction(
                    column=col,
                    issue="Null email values",
                    action_taken="dropped_rows",
                    rows_affected=null_count,
                    before_example="NaN",
                    after_example="Row removed",
                    reason="Email is a critical identifier. Rows without one cannot be contacted or matched.",
                ))
            invalid_mask = ~df[col].apply(is_valid_email)
            bad_count = int(invalid_mask.sum())
            if bad_count > 0:
                example_before = df.loc[invalid_mask, col].iloc[0]
                df = df[~invalid_mask]
                rows_dropped += bad_count
                actions.append(RepairAction(
                    column=col,
                    issue="Malformatted email addresses",
                    action_taken="dropped_rows",
                    rows_affected=bad_count,
                    before_example=str(example_before),
                    after_example="Row removed",
                    reason="Malformatted emails cannot be corrected without knowing the intended value.",
                ))

        # date 
        elif inferred == "date":
            non_std = count_non_standard_dates(df[col])
            if non_std > 0:
                example_before = df[col].dropna().iloc[0]
                df[col] = df[col].apply(
                    lambda x: standardize_date(str(x)) if pd.notna(x) else x
                )
                actions.append(RepairAction(
                    column=col,
                    issue="Inconsistent date formats",
                    action_taken="reformatted",
                    rows_affected=non_std,
                    before_example=str(example_before),
                    after_example=str(standardize_date(str(example_before))),
                    reason="Standardizing to YYYY-MM-DD ensures consistent sorting and parsing.",
                ))

        # categorical 
        elif inferred == "categorical":
            bad_case = detect_case_inconsistency(df[col])
            if bad_case > 0:
                example_before = df[col].dropna().iloc[0]
                df[col] = df[col].apply(
                    lambda x: standardize_case(str(x), "title") if pd.notna(x) else x
                )
                actions.append(RepairAction(
                    column=col,
                    issue="Inconsistent casing in categorical column",
                    action_taken="reformatted",
                    rows_affected=bad_case,
                    before_example=str(example_before),
                    after_example=str(example_before).title(),
                    reason="Inconsistent casing creates duplicate categories in groupby and filter operations.",
                ))
            null_count = int(df[col].isnull().sum())
            if null_count > 0:
                mode_val = df[col].mode()[0] if not df[col].mode().empty else "Unknown"
                df[col] = df[col].fillna(mode_val)
                actions.append(RepairAction(
                    column=col,
                    issue="Null values in categorical column",
                    action_taken="imputed_mode",
                    rows_affected=null_count,
                    before_example="NaN",
                    after_example=str(mode_val),
                    reason="Mode imputation preserves the most common category for categorical data.",
                ))

        # numeric 
        elif inferred == "numeric":
            df[col] = pd.to_numeric(df[col], errors="coerce")
            null_count = int(df[col].isnull().sum())
            if null_count > 0:
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
                actions.append(RepairAction(
                    column=col,
                    issue="Null values in numeric column",
                    action_taken="imputed_median",
                    rows_affected=null_count,
                    before_example="NaN",
                    after_example=str(round(median_val, 4)),
                    reason="Median imputation is robust to skew and outliers.",
                ))

        # id 
        elif inferred == "id":
            null_count = int(df[col].isnull().sum())
            if null_count > 0:
                unresolved.append(
                    f"'{col}' (id): {null_count} null values. ID columns "
                    f"cannot be auto-generated. Manual review required."
                )

        # boolean 
        elif inferred == "boolean":
            null_count = int(df[col].isnull().sum())
            if null_count > 0:
                mode_val = df[col].mode()[0] if not df[col].mode().empty else None
                if mode_val is not None:
                    df[col] = df[col].fillna(mode_val)
                    actions.append(RepairAction(
                        column=col,
                        issue="Null values in boolean column",
                        action_taken="imputed_mode",
                        rows_affected=null_count,
                        before_example="NaN",
                        after_example=str(mode_val),
                        reason="Mode imputation assigns the most common boolean value.",
                    ))

    return df, actions, rows_dropped, unresolved


def run_repairer(
    csv_path: str,
    output_path: str,
    profile: DataProfile,
) -> RepairReport:
    """
    Apply repairs to the dataset and return a structured RepairReport.

    Repairs are applied in Python via apply_repairs. The LLM then receives
    a summary of what was done and produces the structured RepairReport,
    including reasons for each action and any unresolved issues.

    :param csv_path: Path to the raw input CSV.
    :type csv_path: str
    :param output_path: Path to write the cleaned CSV.
    :type output_path: str
    :param profile: DataProfile from the Profiler agent.
    :type profile: DataProfile
    :returns: A RepairReport documenting every action taken and issue left unresolved.
    :rtype: RepairReport
    """
    df = load_dataframe(csv_path)
    original_len = len(df)

    cleaned_df, actions, rows_dropped, unresolved = apply_repairs(df, profile)
    save_dataframe(cleaned_df, output_path)

    prompt = f"""
    Repairs were applied to the dataset at {csv_path}.
    Cleaned output saved to: {output_path}

    Original rows: {original_len}
    Final rows: {len(cleaned_df)}
    Rows dropped: {rows_dropped}

    Actions performed:
    {[a.model_dump() for a in actions]}

    Unresolved issues:
    {unresolved}

    Produce a complete RepairReport documenting these repairs.
    """

    result = repairer_agent.run_sync(prompt)
    return result.output
