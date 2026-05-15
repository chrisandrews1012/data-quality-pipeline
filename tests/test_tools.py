import pandas as pd
import pytest

from src.data_quality_pipeline.tools import (
    analyze_missingness,
    build_missingness_summary,
    clean_numeric_string,
    count_non_numeric,
    count_non_standard_dates,
    detect_case_inconsistency,
    get_column_stats,
    get_dataset_stats,
    is_valid_date,
    is_valid_email,
    standardize_case,
    standardize_date,
)


# clean_numeric_string 

def test_clean_numeric_string_dollar():
    assert clean_numeric_string("$50,000.00") == 50000.0


def test_clean_numeric_string_pound():
    assert clean_numeric_string("£7.25") == 7.25


def test_clean_numeric_string_plain():
    assert clean_numeric_string("75000.0") == 75000.0


def test_clean_numeric_string_none():
    assert clean_numeric_string(None) is None


def test_clean_numeric_string_unparseable():
    assert clean_numeric_string("not a number") is None


# is_valid_email 

def test_valid_email():
    assert is_valid_email("user@example.com") is True


def test_invalid_email_no_at():
    assert is_valid_email("notanemail") is False


def test_invalid_email_no_domain():
    assert is_valid_email("missing@") is False


def test_invalid_email_no_user():
    assert is_valid_email("@nodomain.com") is False


# is_valid_date 

def test_valid_date_iso():
    assert is_valid_date("2023-01-15") is True


def test_valid_date_us_format():
    assert is_valid_date("01/15/2023") is True


def test_valid_date_long_form():
    assert is_valid_date("January 15, 2023") is True


def test_invalid_date():
    assert is_valid_date("not a date") is False


# standardize_date 

def test_standardize_date_us():
    assert standardize_date("01/15/2023") == "2023-01-15"


def test_standardize_date_long():
    assert standardize_date("January 15, 2023") == "2023-01-15"


def test_standardize_date_already_iso():
    assert standardize_date("2023-01-15") == "2023-01-15"


def test_standardize_date_dashed():
    assert standardize_date("15-01-2023") == "2023-01-15"


# standardize_case 

def test_standardize_case_title():
    assert standardize_case("engineering", "title") == "Engineering"


def test_standardize_case_upper():
    assert standardize_case("marketing", "upper") == "MARKETING"


def test_standardize_case_lower():
    assert standardize_case("SALES", "lower") == "sales"


def test_standardize_case_already_title():
    assert standardize_case("Sales", "title") == "Sales"


# detect_case_inconsistency 

def test_detect_case_inconsistency():
    s = pd.Series(["engineering", "Marketing", "Sales", "hr"])
    assert detect_case_inconsistency(s) == 2


def test_detect_case_inconsistency_none():
    s = pd.Series(["Engineering", "Marketing", "Sales"])
    assert detect_case_inconsistency(s) == 0


# count_non_standard_dates 

def test_count_non_standard_dates():
    s = pd.Series(["2023-01-15", "01/15/2023", "January 15, 2023", "2023-02-20"])
    assert count_non_standard_dates(s) == 2


def test_count_non_standard_dates_all_standard():
    s = pd.Series(["2023-01-15", "2023-02-20"])
    assert count_non_standard_dates(s) == 0


# count_non_numeric 

def test_count_non_numeric():
    # "$1,000" is numeric after stripping symbols — only "three thousand" fails
    s = pd.Series(["$1,000", "2000", "three thousand", "4000.50"])
    assert count_non_numeric(s) == 1


def test_count_non_numeric_all_valid():
    s = pd.Series(["1000", "2000.50", "$3,000"])
    assert count_non_numeric(s) == 0


# get_column_stats 

def test_get_column_stats_numeric():
    df = pd.DataFrame({"age": [25, 30, None, 45, 50]})
    stats = get_column_stats(df, "age")
    assert stats["null_count"] == 1
    assert stats["null_pct"] == 20.0
    assert "mean_value" in stats
    assert "min_value" in stats


def test_get_column_stats_text():
    df = pd.DataFrame({"name": ["Alice", "Bob", None, "Charlie"]})
    stats = get_column_stats(df, "name")
    assert stats["null_count"] == 1
    assert "mean_value" not in stats


def test_get_column_stats_sample_values():
    df = pd.DataFrame({"dept": ["Engineering", "Marketing", "Sales", "HR", "Finance"]})
    stats = get_column_stats(df, "dept")
    assert len(stats["sample_values"]) == 5
    assert all(isinstance(v, str) for v in stats["sample_values"])


# get_dataset_stats 

def test_get_dataset_stats():
    df = pd.DataFrame({
        "a": [1, 2, 2, None],
        "b": ["x", "y", "y", "z"],
    })
    stats = get_dataset_stats(df)
    assert stats["row_count"] == 4
    assert stats["duplicate_row_count"] == 1
    assert stats["total_null_count"] == 1


# analyze_missingness

def test_analyze_missingness_no_nulls():
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    result = analyze_missingness(df)
    assert result["columns"] == []


def test_analyze_missingness_mcar():
    import numpy as np
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "age": rng.integers(20, 60, 100).astype(float),
        "score": rng.integers(0, 100, 100).astype(float),
    })
    # Inject small random null rate with no pattern
    df.loc[rng.choice(100, 5, replace=False), "age"] = None
    result = analyze_missingness(df)
    age_result = next(c for c in result["columns"] if c["column"] == "age")
    assert age_result["mechanism"] in ("MCAR", "MAR")
    assert age_result["safe_to_impute"] is True


def test_analyze_missingness_mnar():
    import numpy as np
    rng = np.random.default_rng(7)
    n = 200
    # Random age and salary with no relationship between them
    age = rng.integers(20, 60, n).astype(float)
    salary = rng.uniform(30000, 150000, n)
    df = pd.DataFrame({"salary": salary, "age": age})
    # Randomly null 25% of salary — no correlation with age
    null_idx = rng.choice(n, 50, replace=False)
    df.loc[null_idx, "salary"] = None
    result = analyze_missingness(df)
    salary_result = next((c for c in result["columns"] if c["column"] == "salary"), None)
    assert salary_result is not None
    assert salary_result["safe_to_impute"] is False


# build_missingness_summary 

def test_build_missingness_summary_no_nulls():
    raw = {"columns": [], "dataset_mcar_pvalue": None, "dataset_mcar_conclusion": "no missing data"}
    summary = build_missingness_summary(raw)
    assert "No missing data" in summary


def test_build_missingness_summary_mnar():
    raw = {
        "columns": [
            {"column": "salary", "mechanism": "MNAR", "null_pct": 25.0,
             "null_count": 25, "confidence": "low", "evidence": "...",
             "correlated_with": [], "safe_to_impute": False},
        ],
        "dataset_mcar_pvalue": 0.01,
        "dataset_mcar_conclusion": "not MCAR (p=0.01)",
    }
    summary = build_missingness_summary(raw)
    assert "MNAR" in summary
    assert "salary" in summary
