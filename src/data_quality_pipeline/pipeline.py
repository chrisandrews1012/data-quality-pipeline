import sys
from typing import Callable

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .agents.profiler import run_profiler
from .agents.repairer import run_repairer
from .agents.reporter import run_reporter
from .agents.validator import run_validator
from .invariants import (
    assert_invariants,
    check_profile_invariants,
    check_repair_invariants,
    check_validation_invariants,
)
from .models import PipelineContext
from .tools import load_dataframe

load_dotenv()
console = Console()


def run_pipeline(
    input_path: str = "data/raw/hr_messy.csv",
    output_path: str = "data/processed/cleaned_data.csv",
    report_path: str = "docs/data_quality_report.md",
    progress_callback: Callable[[str], None] | None = None,
) -> PipelineContext:
    """
    Run the full four-agent data quality pipeline.

    Agents run in sequence. Each receives the typed output of the previous
    one. The Repairer runs from the DataProfile only — the ValidationReport
    is passed to the Reporter for documentation but does not drive repairs.

    :param input_path: Path to the raw input CSV.
    :type input_path: str
    :param output_path: Path to write the cleaned CSV.
    :type output_path: str
    :param report_path: Path to write the markdown report.
    :type report_path: str
    :param progress_callback: Optional callable that receives a progress message
        after each agent completes. Used by the web server to stream SSE events.
        When None, progress is printed to the rich console instead.
    :type progress_callback: Callable[[str], None] | None
    :returns: The full PipelineContext bundling all agent outputs.
    :rtype: PipelineContext
    """
    def emit(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)
        else:
            console.print(msg)

    def run_with_progress(fn, task_label):
        if progress_callback:
            return fn()
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as p:
            task = p.add_task(task_label, total=None)
            result = fn()
            p.remove_task(task)
            return result

    if not progress_callback:
        console.print(Panel.fit(
            "[bold cyan]Multi-Agent Data Quality Pipeline[/bold cyan]\n"
            f"Input:  {input_path}\n"
            f"Output: {output_path}\n"
            f"Report: {report_path}",
            border_style="cyan",
        ))

    input_df = load_dataframe(input_path)

    # Agent 1: Profile
    profile = run_with_progress(
        lambda: run_profiler(input_path),
        "[cyan]Agent 1/4: Profiling dataset...",
    )
    assert_invariants(check_profile_invariants(profile, input_df), "Profiler")
    emit(
        f"Profiler complete: {profile.row_count} rows, "
        f"{profile.column_count} columns, {profile.duplicate_row_count} duplicates"
    )

    # Agent 2: Validate
    validation = run_with_progress(
        lambda: run_validator(profile),
        "[cyan]Agent 2/4: Validating dataset...",
    )
    assert_invariants(check_validation_invariants(validation, profile), "Validator")
    status = "Critical issues found" if not validation.passed else "No critical issues"
    emit(
        f"Validator complete: {status} | "
        f"{len(validation.rules_applied)} rules applied | "
        f"{validation.failure_count} findings"
    )

    # Agent 3: Repair
    repair = run_with_progress(
        lambda: run_repairer(input_path, output_path, profile),
        "[cyan]Agent 3/4: Repairing dataset...",
    )
    output_df = load_dataframe(output_path)
    assert_invariants(check_repair_invariants(repair, input_df, output_df), "Repairer")
    emit(
        f"Repairer complete: {repair.total_repairs} repairs, "
        f"{repair.rows_dropped} rows dropped, {len(repair.unresolved)} unresolved"
    )

    # Agent 4: Report
    context = PipelineContext(
        input_path=input_path,
        output_path=output_path,
        profile=profile,
        validation=validation,
        repair=repair,
    )
    run_with_progress(
        lambda: run_reporter(context, report_path),
        "[cyan]Agent 4/4: Writing report...",
    )
    emit(f"Reporter complete: report saved to {report_path}")

    if not progress_callback:
        console.print(Panel.fit(
            "[bold green]Pipeline complete.[/bold green]\n"
            f"Cleaned data: {output_path}\n"
            f"Report:       {report_path}",
            border_style="green",
        ))

    return context


if __name__ == "__main__":
    input_path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/hr_messy.csv"
    run_pipeline(input_path=input_path)
