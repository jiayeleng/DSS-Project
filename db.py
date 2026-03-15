"""
SQLite job database (stdlib sqlite3, no extra dependencies).

Schema
------
jobs
  id               INTEGER  PK autoincrement
  news_url         TEXT     the article URL that triggered this pipeline run
  run_ts           TEXT     ISO-8601 timestamp of the run
  job_index        INTEGER  position within the run (0-based)
  title            TEXT
  employment_status TEXT
  location         TEXT
  tags             TEXT     JSON array — populated later via tag_jobs()
  data_json        TEXT     full job dict as JSON (single source of truth)
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "jobs.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Safe to call multiple times."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                news_url          TEXT    NOT NULL,
                run_ts            TEXT    NOT NULL,
                job_index         INTEGER NOT NULL,
                title             TEXT,
                short_summary     TEXT    DEFAULT '',
                employment_status TEXT,
                location          TEXT,
                tags              TEXT    NOT NULL DEFAULT '[]',
                data_json         TEXT    NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(news_url)"
        )
        # Migration: add short_summary to existing databases that predate this column
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN short_summary TEXT DEFAULT ''")
        except Exception:
            pass  # column already exists


def save_jobs(jobs: list[dict], news_url: str) -> list[int]:
    """
    Persist a list of job dicts to the database.
    Returns the list of new row IDs.
    """
    run_ts = datetime.now(timezone.utc).isoformat()
    row_ids = []
    with _connect() as conn:
        for i, job in enumerate(jobs):
            cur = conn.execute(
                """INSERT INTO jobs
                   (news_url, run_ts, job_index, title, short_summary,
                    employment_status, location, tags, data_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    news_url,
                    run_ts,
                    i,
                    job.get("title"),
                    job.get("short_summary", ""),
                    job.get("employment_status"),
                    job.get("location"),
                    json.dumps([]),          # tags empty until tagged
                    json.dumps(job, ensure_ascii=False),
                ),
            )
            row_ids.append(cur.lastrowid)
    return row_ids


def get_all_jobs() -> list[dict]:
    """Return all jobs, newest run first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, tags, data_json FROM jobs ORDER BY run_ts DESC, job_index ASC"
        ).fetchall()
    result = []
    for row in rows:
        job = json.loads(row["data_json"])
        job["id"] = row["id"]
        job["tags"] = json.loads(row["tags"])
        result.append(job)
    return result


def get_job_by_id(job_id: int) -> Optional[dict]:
    """Return a single job by its database ID, or None if not found."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, tags, data_json FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
    if row is None:
        return None
    job = json.loads(row["data_json"])
    job["id"] = row["id"]
    job["tags"] = json.loads(row["tags"])
    return job


def tag_jobs(job_ids: list[int], tags: list[str]) -> None:
    """
    Attach tags to specific jobs by ID.
    Called later when the 5-question tagging logic is implemented.
    """
    tags_json = json.dumps(tags)
    with _connect() as conn:
        for job_id in job_ids:
            conn.execute(
                "UPDATE jobs SET tags = ? WHERE id = ?",
                (tags_json, job_id),
            )
