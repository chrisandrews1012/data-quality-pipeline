import uuid
from typing import Literal


JobStatus = Literal["pending", "running", "complete", "error"]

_jobs: dict[str, dict] = {}


def create_job() -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "pending",
        "events": [],
        "output_path": None,
        "report_path": None,
        "tmp_dir": None,
        "error_message": None,
    }
    return job_id


def append_event(job_id: str, message: str) -> None:
    _jobs[job_id]["events"].append(message)


def set_running(job_id: str) -> None:
    _jobs[job_id]["status"] = "running"


def complete_job(job_id: str, output_path: str, report_path: str, tmp_dir: str) -> None:
    _jobs[job_id].update({
        "status": "complete",
        "output_path": output_path,
        "report_path": report_path,
        "tmp_dir": tmp_dir,
    })


def fail_job(job_id: str, error_message: str) -> None:
    _jobs[job_id].update({
        "status": "error",
        "error_message": error_message,
    })


def get_job(job_id: str) -> dict | None:
    return _jobs.get(job_id)
