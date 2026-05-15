# Data Quality Report — messy_data

## Executive Summary

The messy_data dataset contained 520 rows across 9 columns, with several quality issues ranging from duplicate records and invalid age values to missing contact information and incorrect data types. Four critical failures and two warnings were identified during validation. A total of 79 rows were dropped and 10 repair actions were applied across 7 columns, reducing the dataset to 441 clean rows. The cleaned file has been saved and is ready for downstream use, with no unresolved issues remaining.

---

## Dataset Overview

| Metric | Value |
|---|---|
| Row Count | 520 |
| Column Count | 9 |
| Duplicate Rows | 20 |
| Total Nulls | 84 |
| Columns Profiled | 9 |

---

## Column Profile

| Column | Inferred Type | Null % | Unique % | Notable Observations |
|---|---|---|---|---|
| employee_id | ID | 0.0% | 96.15% | Only 500 unique values across 520 rows: primary key integrity violated |
| name | Text | 0.0% | 95.77% | Clean. Two non-unique names suggest possible duplicates or coincidence |
| email | Email | 7.69% | 86.15% | 40 nulls; some malformatted entries (e.g., `missing@`) |
| age | Age | 4.62% | 13.27% | Min: -5.0, Max: 999.0, Std: 47.8: severe outliers present |
| gender | Categorical | 0.0% | 0.58% | 3 categories: inconsistent casing detected |
| salary | Currency | 3.85% | 92.31% | Stored as string dtype: some values contain currency symbols and commas |
| department | Categorical | 0.0% | 1.92% | 10 categories: inconsistent casing detected |
| hire_date | Date | 0.0% | 90.19% | Inconsistent date formats present across rows |
| is_active | Boolean | 0.0% | 0.38% | Exactly 2 values (True/False): clean |

---

## Missingness Analysis

The dataset-level Little's MCAR test could not be performed due to insufficient numeric columns. The table below summarises per-column missingness findings.

| Column | Mechanism | Confidence | Null % | Evidence |
|---|---|---|---|---|
| email | MCAR | Medium | 7.69% | Low null rate with no significant correlation to other columns: safe to impute |
| age | MCAR | Medium | 4.62% | Low null rate with no significant correlation to other columns: safe to impute |
| salary | MCAR | Medium | 3.85% | Low null rate with no significant correlation to other columns: safe to impute |

No MNAR findings were identified. However, users should note that email nulls were resolved by row removal rather than imputation, as fabricating contact addresses would introduce false data into the record.

---

## Validation Findings

| Column | Severity | Description | Suggested Fix |
|---|---|---|---|
| employee_id | 🔴 Critical | Only 96.15% unique (500/520 rows): primary key integrity violated by ~20 duplicate UUIDs | Deduplicate rows and assign unique UUIDs to any legitimate separate employees sharing an ID |
| email | 🔴 Critical | 40 null values (7.69%): email is a critical identifier and should be fully populated | Retrieve missing addresses from HR systems: use a placeholder if unavailable |
| age | 🔴 Critical | Min: -5.0, Max: 999.0: biologically impossible values present across at least 11 rows | Nullify all values outside [0, 120]: re-source from HR: apply a CHECK constraint at source |
| salary | 🔴 Critical | Stored as `str` dtype instead of numeric: 20 nulls (3.85%) also present | Cast to float64 after stripping symbols and commas: impute nulls with median by department |
| _dataset_ | 🟡 Warning | 20 fully duplicate rows detected: will inflate headcounts and aggregates | Drop duplicates: investigate pipeline for double-ingestion as root cause |
| age | 🟡 Warning | 24 null values (4.62%): MCAR: safe to impute only after out-of-range values are resolved | Impute with median age after outlier removal: document methodology for audit |

---

## Rules Applied

| Column | Rule Description | Severity | Passed |
|---|---|---|---|
| employee_id | ID column must have zero nulls and ~100% uniqueness | 🔴 Critical | ❌ |
| name | Text column must not have very high null rates | 🔵 Info | ✅ |
| email | Email column must have zero nulls and all non-null values must match a valid email format | 🔴 Critical | ❌ |
| age | Age must be numeric and all values must fall within the valid range 0–120 | 🔴 Critical | ❌ |
| age | Age column must have a low null rate (MCAR): nulls should be reviewed or imputed | 🟡 Warning | ❌ |
| gender | Categorical column must have low null rate and consistent casing: note low cardinality | 🔵 Info | ✅ |
| salary | Currency column must be numeric: flag values with currency symbols, commas, or non-numeric content | 🔴 Critical | ❌ |
| salary | Currency column must have low null rate (MCAR): nulls should be reviewed or imputed | 🟡 Warning | ✅ |
| department | Categorical column must have low null rate and consistent casing: note low cardinality | 🔵 Info | ✅ |
| hire_date | Date column must have consistent formats and all values must be parseable as dates | 🟡 Warning | ✅ |
| is_active | Boolean column must contain exactly 2 distinct values and have zero nulls | 🔴 Critical | ✅ |
| _dataset_ | Dataset must have zero duplicate rows | 🟡 Warning | ❌ |

---

## Repairs Applied

| Column | Issue | Action Taken | Rows Affected | Before Example | After Example |
|---|---|---|---|---|---|
| (all columns) | Duplicate rows | Dropped rows | 20 | Identical row appearing multiple times | One copy retained: duplicates removed |
| email | Null email values | Dropped rows | 39 | `NaN` | Row removed |
| email | Malformatted email addresses | Dropped rows | 20 | `missing@` | Row removed |
| age | Out-of-range values (< 0 or > 120) | Flagged: set to NaN | 11 | `-1.0` | `NaN` |
| age | Null age values (including flagged outliers) | Imputed with median | 31 | `NaN` | `51.0` |
| gender | Inconsistent casing | Reformatted to title case | 143 | `Non-binary` | `Non-Binary` |
| salary | Currency symbols and commas in numeric field | Reformatted: symbols stripped | 18 | `$69,682.09` | `69682.09` |
| salary | Null values | Imputed with median | 19 | `NaN` | `87933.42` |
| department | Inconsistent casing | Reformatted | 127 | `HR` | `Hr` |
| hire_date | Inconsistent date formats | Reformatted to ISO 8601 | 28 | `2019-03-07` | `2019-03-07` |

---

## Unresolved Issues

None. All issues resolved.

---

## Before vs After

| Metric | Before | After |
|---|---|---|
| Row Count | 520 | 441 |
| Null Count | 84 | 0 |
| Duplicate Count | 20 | 0 |

---

## Recommendations

- **Enforce a primary key constraint at source:** Employee IDs should be generated as guaranteed-unique UUIDs by the originating system: never reused or duplicated at ingestion.
- **Make email a required field at the point of entry:** HR and onboarding forms should prevent submission without a valid, formatted email address to eliminate nulls and malformed entries upstream.
- **Apply database-level CHECK constraints for age:** A constraint such as `age BETWEEN 0 AND 120` should be enforced at the database or API validation layer to prevent impossible values from ever reaching the pipeline.
- **Store salary as a numeric type from the source:** Financial fields should be written as decimal or float values in the source system: currency symbols and thousands separators belong only in display formatting, not stored data.
- **Standardise categorical values and date formats in the ingestion pipeline:** A lookup table or enum constraint for `gender` and `department` will prevent casing inconsistencies: all dates should be written in ISO 8601 format (YYYY-MM-DD) at the point of capture.