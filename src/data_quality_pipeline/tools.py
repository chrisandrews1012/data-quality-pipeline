import os
import re
import numpy as np
import pandas as pd


# I/O 

def load_dataframe(path: str) -> pd.DataFrame:
    """
    Load a CSV file into a pandas DataFrame.

    :param path: Absolute or relative path to the CSV file.
    :type path: str
    :returns: DataFrame containing the CSV contents.
    :rtype: pd.DataFrame
    """
    return pd.read_csv(path)


def save_dataframe(df: pd.DataFrame, path: str) -> None:
    """
    Save a DataFrame to CSV, creating parent directories if needed.

    :param df: DataFrame to save.
    :type df: pd.DataFrame
    :param path: Destination file path.
    :type path: str
    :returns: None
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False)


# Column Statistics 

def get_column_stats(df: pd.DataFrame, col: str) -> dict:
    """
    Compute per-column statistics to pass to the Profiler agent.

    Pre-computing these in Python keeps the LLM grounded in real numbers
    rather than asking it to calculate statistics itself. Numeric-only
    fields (min, max, mean, std) are omitted for non-numeric columns.

    :param df: The full dataset.
    :type df: pd.DataFrame
    :param col: Name of the column to profile.
    :type col: str
    :returns: Dictionary of statistics for the column.
    :rtype: dict
    """
    s = df[col]
    n = len(s)

    stats: dict = {
        "dtype": str(s.dtype),
        "null_count": int(s.isnull().sum()),
        "null_pct": round(s.isnull().mean() * 100, 2),
        "unique_count": int(s.nunique()),
        "unique_pct": round(s.nunique() / n * 100, 2) if n > 0 else 0.0,
        "sample_values": [
            str(v) for v in s.dropna().sample(
                min(5, s.dropna().shape[0]), random_state=42
            ).tolist()
        ],
    }

    if pd.api.types.is_numeric_dtype(s):
        stats["min_value"] = str(round(float(s.min()), 4)) if not s.isnull().all() else None
        stats["max_value"] = str(round(float(s.max()), 4)) if not s.isnull().all() else None
        stats["mean_value"] = round(float(s.mean()), 4) if not s.isnull().all() else None
        stats["std_value"] = round(float(s.std()), 4) if not s.isnull().all() else None

    return stats


def get_dataset_stats(df: pd.DataFrame) -> dict:
    """
    Compute top-level dataset statistics.

    :param df: The full dataset.
    :type df: pd.DataFrame
    :returns: Dictionary with row_count, column_count, duplicate_row_count,
              and total_null_count.
    :rtype: dict
    """
    return {
        "row_count": len(df),
        "column_count": len(df.columns),
        "duplicate_row_count": int(df.duplicated().sum()),
        "total_null_count": int(df.isnull().sum().sum()),
    }


# Validators 

def is_valid_email(value: str) -> bool:
    """
    Check whether a string matches a valid email format.

    :param value: The value to test.
    :type value: str
    :returns: True if the value matches a standard email pattern.
    :rtype: bool
    """
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, str(value)))


def is_numeric_string(value) -> bool:
    """
    Check whether a value can be parsed as a number.

    Handles common formatting like currency symbols and thousands separators
    (e.g. ``$1,000.00``, ``£7.25``).

    :param value: The value to test.
    :returns: True if the value is numeric after stripping symbols.
    :rtype: bool
    """
    if pd.isna(value):
        return False
    try:
        float(str(value).replace("$", "").replace(",", "").replace("£", "").strip())
        return True
    except ValueError:
        return False


def is_valid_date(value: str) -> bool:
    """
    Check whether a string can be parsed as a date.

    Uses ``dateutil.parser`` which handles a wide range of formats.

    :param value: The value to test.
    :type value: str
    :returns: True if the value is parseable as a date.
    :rtype: bool
    """
    from dateutil import parser as dateparser
    try:
        dateparser.parse(str(value))
        return True
    except Exception:
        return False


# Cleaners 

def clean_numeric_string(value) -> float | None:
    """
    Strip currency symbols and commas from a numeric string and return a float.

    Handles ``$``, ``£``, ``€``, and comma thousands separators.
    Returns ``None`` for null input or values that cannot be converted.

    :param value: The value to clean.
    :returns: Cleaned float value, or None if conversion fails.
    :rtype: float | None
    """
    if pd.isna(value):
        return None
    try:
        return float(
            str(value)
            .replace("$", "")
            .replace("£", "")
            .replace("€", "")
            .replace(",", "")
            .strip()
        )
    except ValueError:
        return None


def standardize_date(value: str) -> str | None:
    """
    Parse any date string and return it in ``YYYY-MM-DD`` format.

    Uses ``dateutil.parser`` to handle virtually any input format.
    Returns ``None`` if the value cannot be parsed.

    :param value: The date string to standardize.
    :type value: str
    :returns: Date string in YYYY-MM-DD format, or None on failure.
    :rtype: str | None
    """
    from dateutil import parser as dateparser
    try:
        return str(dateparser.parse(str(value)).date())
    except Exception:
        return None


def standardize_case(value: str, style: str = "title") -> str:
    """
    Standardize the case of a string value.

    :param value: The string to transform.
    :type value: str
    :param style: One of ``'title'``, ``'upper'``, or ``'lower'``.
                  Defaults to ``'title'``.
    :type style: str
    :returns: The string in the requested case, or the original value if null.
    :rtype: str
    """
    if pd.isna(value):
        return value
    if style == "title":
        return str(value).title()
    elif style == "upper":
        return str(value).upper()
    else:
        return str(value).lower()


# Repair Helpers 

def count_invalid_emails(series: pd.Series) -> int:
    """
    Count non-null values in a Series that fail email validation.

    :param series: Column to check.
    :type series: pd.Series
    :returns: Number of non-null values that are not valid email addresses.
    :rtype: int
    """
    return int((~series.dropna().apply(is_valid_email)).sum())


def count_non_numeric(series: pd.Series) -> int:
    """
    Count non-null values in a Series that cannot be parsed as numbers.

    :param series: Column to check.
    :type series: pd.Series
    :returns: Number of non-null values that are not numeric.
    :rtype: int
    """
    return int((~series.dropna().apply(is_numeric_string)).sum())


def count_non_standard_dates(series: pd.Series) -> int:
    """
    Count values in a Series that are not in ``YYYY-MM-DD`` format.

    :param series: Column to check.
    :type series: pd.Series
    :returns: Number of non-null values that do not match YYYY-MM-DD.
    :rtype: int
    """
    pattern = r"^\d{4}-\d{2}-\d{2}$"
    return int((~series.dropna().astype(str).str.match(pattern)).sum())


def detect_case_inconsistency(series: pd.Series) -> int:
    """
    Count values in a Series that differ from their title-cased version.

    Used to detect mixed-case categorical columns such as a ``department``
    column containing both ``"engineering"`` and ``"Engineering"``.

    :param series: Column to check.
    :type series: pd.Series
    :returns: Number of non-null values that are not already title-cased.
    :rtype: int
    """
    return int(
        series.dropna().apply(lambda x: str(x) != str(x).title()).sum()
    )


# Missingness Mechanism Detection 

def analyze_missingness(df: pd.DataFrame) -> dict:
    """
    Classify the missing data mechanism for each column with null values.

    For each column with nulls, tests whether missingness is correlated with
    other numeric columns using point-biserial correlation (MAR signal).
    Columns with high null rates and no detectable correlate are flagged as
    potentially MNAR. Also runs a dataset-level Little's MCAR test.

    :param df: The full dataset.
    :type df: pd.DataFrame
    :returns: Dictionary with keys ``columns`` (list of per-column results)
              and ``dataset_mcar_pvalue`` / ``dataset_mcar_conclusion``.
    :rtype: dict
    """
    from scipy import stats as scipy_stats

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cols_with_nulls = [c for c in df.columns if df[c].isnull().any()]
    column_results = []

    for col in cols_with_nulls:
        null_pct = df[col].isnull().mean()
        missing_indicator = df[col].isnull().astype(int)
        correlated_with = []

        for other in numeric_cols:
            if other == col:
                continue
            valid = df[other].notna()
            if valid.sum() < 20:
                continue
            corr, pval = scipy_stats.pointbiserialr(
                missing_indicator[valid], df[other][valid]
            )
            if pval < 0.05 and abs(corr) > 0.1:
                correlated_with.append(other)

        if correlated_with:
            mechanism = "MAR"
            confidence = "high" if len(correlated_with) >= 2 else "medium"
            evidence = (
                f"Missingness significantly correlated with: {', '.join(correlated_with)}. "
                f"Imputation is valid but conditioning on these columns improves accuracy."
            )
            safe_to_impute = True
        elif null_pct > 0.20:
            mechanism = "MNAR"
            confidence = "low"
            evidence = (
                f"{null_pct:.0%} missing with no detectable correlation to other columns. "
                f"Values may be absent because of the value itself. "
                f"Imputation would introduce systematic bias."
            )
            safe_to_impute = False
        else:
            mechanism = "MCAR"
            confidence = "medium"
            evidence = (
                f"Low null rate ({null_pct:.0%}) with no significant correlation "
                f"to other columns. Safe to impute."
            )
            safe_to_impute = True

        column_results.append({
            "column": col,
            "null_count": int(df[col].isnull().sum()),
            "null_pct": round(null_pct * 100, 2),
            "mechanism": mechanism,
            "confidence": confidence,
            "evidence": evidence,
            "correlated_with": correlated_with,
            "safe_to_impute": safe_to_impute,
        })

    mcar_pvalue = None
    mcar_conclusion = "insufficient numeric columns for test"
    if len(numeric_cols) >= 2 and df[numeric_cols].isnull().any().any():
        try:
            mcar_pvalue, mcar_conclusion = _little_mcar_test(df[numeric_cols])
        except Exception:
            mcar_conclusion = "test could not be computed"

    return {
        "columns": column_results,
        "dataset_mcar_pvalue": mcar_pvalue,
        "dataset_mcar_conclusion": mcar_conclusion,
    }


def _little_mcar_test(df: pd.DataFrame) -> tuple[float | None, str]:
    """
    Simplified Little's MCAR test.

    Groups rows by their missingness pattern and tests whether each group's
    column means deviate from the overall means more than chance allows,
    using a chi-square statistic. A p-value above 0.05 means we fail to
    reject MCAR; below 0.05 means the data is likely MAR or MNAR.

    :param df: Numeric-only subset of the dataset.
    :type df: pd.DataFrame
    :returns: Tuple of (p_value, conclusion_string). p_value is None if
              the test could not be computed.
    :rtype: tuple[float | None, str]
    """
    from scipy import stats as scipy_stats

    miss_matrix = df.isnull().astype(int)
    pattern_series = miss_matrix.apply(tuple, axis=1)
    unique_patterns = pattern_series.unique()

    if len(unique_patterns) == 1:
        return (1.0, "MCAR: single missingness pattern (all rows have same observed columns)")

    overall_means = df.mean()
    overall_cov = df.cov()
    d_sq = 0.0
    dof = 0

    for pattern in unique_patterns:
        mask = pattern_series == pattern
        n_k = int(mask.sum())
        if n_k < 2:
            continue
        observed_cols = [c for c, m in zip(df.columns, pattern) if m == 0]
        if not observed_cols:
            continue
        group_means = df.loc[mask, observed_cols].mean()
        diff = (group_means - overall_means[observed_cols]).values
        sub_cov = overall_cov.loc[observed_cols, observed_cols].values
        try:
            cov_inv = np.linalg.pinv(sub_cov)
            d_sq += n_k * float(diff @ cov_inv @ diff)
            dof += len(observed_cols)
        except Exception:
            continue

    if dof == 0:
        return (None, "could not compute: no valid patterns")

    p_value = round(float(1 - scipy_stats.chi2.cdf(d_sq, df=dof)), 4)
    if p_value > 0.05:
        conclusion = f"MCAR (p={p_value} > 0.05): fail to reject null hypothesis"
    else:
        conclusion = f"not MCAR (p={p_value} <= 0.05): missingness is likely MAR or MNAR"

    return (p_value, conclusion)


def build_missingness_summary(raw: dict) -> str:
    """
    Generate a plain English summary from the output of ``analyze_missingness``.

    :param raw: The dictionary returned by ``analyze_missingness``.
    :type raw: dict
    :returns: A one-paragraph summary suitable for the DataProfile summary field.
    :rtype: str
    """
    cols = raw["columns"]
    if not cols:
        return "No missing data detected."
    mnar = [c["column"] for c in cols if c["mechanism"] == "MNAR"]
    mar  = [c["column"] for c in cols if c["mechanism"] == "MAR"]
    mcar = [c["column"] for c in cols if c["mechanism"] == "MCAR"]
    parts = []
    if mnar:
        parts.append(
            f"{len(mnar)} column(s) flagged as potentially MNAR "
            f"({', '.join(mnar)}). Imputation not recommended."
        )
    if mar:
        parts.append(
            f"{len(mar)} column(s) classified as MAR "
            f"({', '.join(mar)}). Safe to impute."
        )
    if mcar:
        parts.append(f"{len(mcar)} column(s) classified as MCAR. Safe to impute.")
    parts.append(f"Dataset-level test: {raw['dataset_mcar_conclusion']}.")
    return " ".join(parts)
