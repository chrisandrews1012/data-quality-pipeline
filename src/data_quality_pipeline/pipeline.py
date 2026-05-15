import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .agents.profiler import run_profiler
from .agents.repairer import run_repairer
from .agents.reporter import run_reporter
from .agents.validator import run_validator
from .models import PipelineContext

load_dotenv()
console = Console()


def run_pipeline(
    input_path: str = "data/raw/messy_data.csv",
    output_path: str = "data/processed/cleaned_data.csv",
    report_path: str = "docs/data_quality_report.md",
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
    :returns: The full PipelineContext bundling all agent outputs.
    :rtype: PipelineContext
    """
    console.print(Panel.fit(
        "[bold cyan]Multi-Agent Data Quality Pipeline[/bold cyan]\n"
        f"Input:  {input_path}\n"
        f"Output: {output_path}\n"
        f"Report: {report_path}",
        border_style="cyan",
    ))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:

        # Agent 1: Profile
        task = progress.add_task("[cyan]Agent 1/4: Profiling dataset...", total=None)
        profile = run_profiler(input_path)
        progress.remove_task(task)
        console.print(
            f"[green]Profiler complete.[/green] "
            f"{profile.row_count} rows, {profile.column_count} columns, "
            f"{profile.duplicate_row_count} duplicates"
        )

        # Agent 2: Validate
        task = progress.add_task("[cyan]Agent 2/4: Validating dataset...", total=None)
        validation = run_validator(profile)
        progress.remove_task(task)
        status = "[red]FAILED[/red]" if not validation.passed else "[green]PASSED[/green]"
        console.print(
            f"[green]Validator complete.[/green] "
            f"Status: {status} | "
            f"{len(validation.rules_applied)} rules applied | "
            f"{validation.failure_count} failures"
        )

        # Agent 3: Repair
        task = progress.add_task("[cyan]Agent 3/4: Repairing dataset...", total=None)
        repair = run_repairer(input_path, output_path, profile)
        progress.remove_task(task)
        console.print(
            f"[green]Repairer complete.[/green] "
            f"{repair.total_repairs} repairs, "
            f"{repair.rows_dropped} rows dropped, "
            f"{len(repair.unresolved)} unresolved"
        )

        # Agent 4: Report
        task = progress.add_task("[cyan]Agent 4/4: Writing report...", total=None)
        context = PipelineContext(
            input_path=input_path,
            output_path=output_path,
            profile=profile,
            validation=validation,
            repair=repair,
        )
        run_reporter(context, report_path)
        progress.remove_task(task)
        console.print(f"[green]Reporter complete.[/green] Report saved to {report_path}")

    console.print(Panel.fit(
        "[bold green]Pipeline complete.[/bold green]\n"
        f"Cleaned data: {output_path}\n"
        f"Report:       {report_path}",
        border_style="green",
    ))

    return context


if __name__ == "__main__":
    input_path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/messy_data.csv"
    run_pipeline(input_path=input_path)
