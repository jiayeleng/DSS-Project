"""
Export jobs from jobs.db in a human-readable TXT format (like output/jobs_*.txt),
and optionally export JSON.

Requirement handled:
- Display `summary` as `Ecological Context & System Conditions`.

Usage:
    python export_10_jobs.py
    python export_10_jobs.py --count 10
    python export_10_jobs.py --txt-out output/jobs_export_10.txt
    python export_10_jobs.py --json-out output/exported_10_jobs.json
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

import db

SEPARATOR = "=" * 60
JOB_SEPARATOR = "─" * 60


def _ensure_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _transform_job(job: dict) -> dict:
    """Return a copy of job with field rename for export."""
    out = dict(job)
    if "summary" in out:
        out["Ecological Context & System Conditions"] = out.pop("summary")
    return out


def _render_job_text(job: dict, idx: int) -> str:
    title = job.get("title", "Untitled Job")
    short_summary = job.get("short_summary", "")

    lines: list[str] = []
    lines.append(JOB_SEPARATOR)
    lines.append(f"Job {idx}: {title}")
    lines.append(JOB_SEPARATOR)
    lines.append("")

    if short_summary:
        lines.append(short_summary)
        lines.append("")

    lines.append(f"  Employment : {job.get('employment_status', '—')}")
    lines.append(f"  Salary     : {job.get('salary_range', '—')}")
    lines.append(f"  Location   : {job.get('location', '—')}")
    lines.append(f"  Duration   : {job.get('duration', '—')}")
    lines.append("")

    responsibilities = _ensure_list(job.get("responsibilities"))
    if responsibilities:
        lines.append("  Responsibilities:")
        for item in responsibilities:
            lines.append(f"    • {item}")
        lines.append("")

    qualifications = _ensure_list(job.get("qualifications"))
    if qualifications:
        lines.append("  Qualifications:")
        for item in qualifications:
            lines.append(f"    • {item}")
        lines.append("")

    benefits = _ensure_list(job.get("benefits"))
    if benefits:
        lines.append("  Benefits:")
        for item in benefits:
            lines.append(f"    • {item}")
        lines.append("")

    eco_context = job.get("Ecological Context & System Conditions", "")
    if eco_context:
        lines.append("  Ecological Context & System Conditions:")
        lines.append(f"    {eco_context}")
        lines.append("")

    references = _ensure_list(job.get("references"))
    if references:
        lines.append("  References:")
        for i, ref in enumerate(references, start=1):
            lines.append(f"    [{i}] {ref}")
        lines.append("")

    return "\n".join(lines).rstrip()


def export_jobs(count: int, txt_out: str, json_out: str | None) -> None:
    db.init_db()
    jobs = db.get_all_jobs()
    selected = [_transform_job(job) for job in jobs[:count]]

    os.makedirs(os.path.dirname(txt_out) or ".", exist_ok=True)

    text_parts = [SEPARATOR, "RECOMMENDED JOBS", SEPARATOR, ""]
    for idx, job in enumerate(selected, start=1):
        text_parts.append(_render_job_text(job, idx))
        text_parts.append("")
    text_parts.append(SEPARATOR)

    with open(txt_out, "w", encoding="utf-8") as f:
        f.write("\n".join(text_parts).rstrip() + "\n")

    print(f"TXT exported: {txt_out}")

    if json_out:
        os.makedirs(os.path.dirname(json_out) or ".", exist_ok=True)
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(selected, f, ensure_ascii=False, indent=2)
        print(f"JSON exported: {json_out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export jobs in readable TXT format")
    parser.add_argument("--count", type=int, default=10, help="Number of jobs to export (default: 10)")
    parser.add_argument(
        "--txt-out",
        default="output/jobs_export_10.txt",
        help="Readable TXT output path (default: output/jobs_export_10.txt)",
    )
    parser.add_argument(
        "--json-out",
        default=None,
        help="Optional JSON output path, e.g. output/exported_10_jobs.json",
    )

    args = parser.parse_args()
    export_jobs(args.count, args.txt_out, args.json_out)
