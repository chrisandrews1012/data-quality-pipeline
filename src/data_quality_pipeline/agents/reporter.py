import os

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel

from ..models import PipelineContext

model = AnthropicModel("claude-sonnet-4-6")

reporter_agent = Agent(
    model=model,
    output_type=str,
    system_prompt="""
    You are a data quality reporter. You receive a complete pipeline context
    and produce a professional markdown report.

    Structure the report exactly as follows:

    # Data Quality Report — {dataset_name}

    ## Executive Summary
    3-4 sentences in plain English. No jargon. Suitable for a non-technical
    stakeholder. Summarise what was found and what was done.

    ## Dataset Overview
    A markdown table with: row count, column count, duplicate rows,
    total nulls, columns profiled.

    ## Column Profile
    A markdown table with one row per column showing: name, inferred type,
    null %, unique %, and any notable observations.

    ## Missingness Analysis
    State the dataset-level Little's MCAR test result in one sentence.
    Then produce a markdown table with one row per column that had missing values:
    column | mechanism | confidence | null % | evidence
    End with one sentence explaining what any MNAR finding means for
    downstream users of this dataset.

    ## Validation Findings
    A markdown table of all failures with: column, severity, description,
    suggested fix. Use emoji for severity: 🔴 critical, 🟡 warning, 🔵 info.

    ## Rules Applied
    A markdown table of all rules the validator inferred and applied,
    even passing ones. Shows the reader the agent actually reasoned about
    the dataset.

    ## Repairs Applied
    A markdown table of: column, issue, action taken, rows affected,
    before example, after example.

    ## Unresolved Issues
    Bullet list of issues that could not be automatically repaired
    and require manual review. If none, write "None. All issues resolved."

    ## Before vs After
    A comparison table showing key metrics before and after repair:
    row count, null count, duplicate count.

    ## Recommendations
    3-5 bullet points for the data owner on how to prevent these issues
    at the source.

    Be concise. Use markdown tables throughout. Do not add any preamble
    or postamble outside the report structure above.
    Do not use dashes in sentences. Use colons or periods instead.
    """,
)


def run_reporter(
    context: PipelineContext,
    output_path: str = "docs/data_quality_report.md",
) -> str:
    """
    Generate a markdown report from the full pipeline context and save it to disk.

    The reporter is the only agent that receives the complete PipelineContext,
    giving it visibility into the profile, validation findings, and repair
    actions simultaneously. The report is written for both technical and
    non-technical audiences.

    :param context: The full pipeline context bundling profile, validation, and repair.
    :type context: PipelineContext
    :param output_path: Path to write the markdown report. Created if it does not exist.
    :type output_path: str
    :returns: The generated markdown report as a string.
    :rtype: str
    """
    prompt = f"""
    Generate a complete data quality report from this pipeline context:

    {context.model_dump_json(indent=2)}
    """

    result = reporter_agent.run_sync(prompt)
    report_md = result.output

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(report_md)

    return report_md
