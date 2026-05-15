from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel

from ..models import DataProfile, ValidationReport

model = AnthropicModel("claude-sonnet-4-6")

validator_agent = Agent(
    model=model,
    output_type=ValidationReport,
    system_prompt="""
    You are a data validation agent. You receive a data profile where each
    column has an inferred semantic type. Your job is to infer appropriate
    validation rules for each column based on its type, then apply them
    and return a ValidationReport.

    Use these rules per semantic type:

      id          - must have zero nulls; uniqueness should be ~100%
      email       - zero nulls expected; all non-null values must match email format
      phone       - flag high null rates; check for consistent formatting
      age         - must be numeric; flag values outside 0-120
      date        - flag inconsistent formats; all values should be parseable as dates
      currency    - must be numeric (flag values with currency symbols or commas)
      categorical - flag high null rates; check for inconsistent casing; note low cardinality
      numeric     - flag extreme outliers (beyond 3 std devs); flag high null rates
      boolean     - should only contain 2 distinct values; flag nulls
      text        - flag very high null rates only
      unknown     - flag high null rates; no other rules applied

    Severity:
      critical - data is unusable without fixing this (nulls in ID, wrong dtype)
      warning  - degrades quality but data is still usable (inconsistent casing, outliers)
      info     - minor issue worth noting (low cardinality, sparse column)

    Always check for duplicate rows regardless of column types.
    Set passed=True only if there are zero critical failures.
    Document every rule you applied in rules_applied, even passing ones.

    You will also receive a missingness analysis for each column. Use the
    mechanism field to inform severity:
      MNAR columns with nulls should always be flagged as critical, since
      imputation would bias results and manual review is required.
      MAR and MCAR columns follow the standard severity rules above.
    """,
)


def run_validator(profile: DataProfile) -> ValidationReport:
    """
    Infer and apply validation rules based on the DataProfile.

    No rules are hardcoded. The agent adapts to whatever dataset it receives
    by reading the inferred semantic type for each column and deciding which
    rules apply. Missingness mechanism is included in the profile so the
    agent can escalate severity for MNAR columns.

    :param profile: The DataProfile produced by the Profiler agent.
    :type profile: DataProfile
    :returns: A ValidationReport containing all rules applied and any failures found.
    :rtype: ValidationReport
    """
    prompt = f"""
    Validate this dataset. Infer appropriate rules from the column semantic
    types and apply them. Return a complete ValidationReport.

    Dataset profile:
    {profile.model_dump_json(indent=2)}
    """
    result = validator_agent.run_sync(prompt)
    return result.output
