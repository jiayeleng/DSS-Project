"""
FastAPI server — exposes the job database to the React frontend.

Run:
    uvicorn server:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import db

app = FastAPI(title="Ecology Job Recommender")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

db.init_db()


class UserAnswers(BaseModel):
    lifeSystems:        str = ""   # plants / animals / environmental systems
    habitatDomain:      str = ""   # land / water / air
    circadianPhase:     str = ""   # day / night
    operationalSetting: str = ""   # indoor / field work
    interactionMode:    str = ""   # observe / help / touch


@app.post("/api/jobs")
def get_jobs(answers: UserAnswers) -> list[dict]:
    """
    Return a ranked list of jobs (not just one random batch).

    Jobs are grouped by tag overlap score with user's selections (5 → 0),
    then each score tier is shuffled and concatenated. Frontend paginates the
    stable list into batches (next/previous) to avoid duplicate reshuffles.

    If strict matching yields too few jobs, we still include lower-score tiers,
    so users can keep browsing and always get additional batches.
    """
    import random

    jobs = db.get_all_jobs()
    if not jobs:
      return []

    selected = {v for v in [
        answers.lifeSystems,
        answers.habitatDomain,
        answers.circadianPhase,
        answers.operationalSetting,
        answers.interactionMode,
    ] if v}

    if not selected:
        random.shuffle(jobs)
        return jobs

    def score(job):
        return len(selected & set(job.get("tags") or []))

    # Group jobs by score (5 → 0), shuffle inside each tier for diversity.
    tiers: dict[int, list] = {}
    for j in jobs:
        s = score(j)
        tiers.setdefault(s, []).append(j)

    ranked = []
    for s in range(5, -1, -1):
        tier = tiers.get(s, [])
        if not tier:
            continue
        random.shuffle(tier)
        ranked.extend(tier)

    return ranked


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int) -> dict:
    """Return the full details for a single job as JSON."""
    job = db.get_job_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail_page(job_id: int):
    """Human-readable job detail page — linked from QR codes."""
    job = db.get_job_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    def _list_items(items):
        if not items:
            return ""
        return "".join(f"<li>{item}</li>" for item in items)

    def _refs(items):
        if not items:
            return ""
        parts = []
        for ref in items:
            # turn URL in reference string into a link
            import re
            ref_linked = re.sub(
                r'(https?://\S+)',
                r'<a href="\1" target="_blank">\1</a>',
                ref,
            )
            parts.append(f"<li>{ref_linked}</li>")
        return "".join(parts)

    responsibilities_html = _list_items(job.get("responsibilities", []))
    qualifications_html   = _list_items(job.get("qualifications", []))
    benefits_html         = _list_items(job.get("benefits", []))
    references_html       = _refs(job.get("references", []))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{job.get('title', 'Job Detail')} — DSS</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #0a0c0a;
      color: #c8cfc4;
      padding: 2rem 1.25rem 4rem;
      max-width: 680px;
      margin: 0 auto;
      line-height: 1.65;
    }}
    .label {{
      font-size: 0.72rem;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      color: #7aab6e;
      margin-bottom: 0.5rem;
    }}
    h1 {{
      font-size: 1.4rem;
      font-weight: 500;
      color: #e8ede4;
      margin-bottom: 1.5rem;
      line-height: 1.3;
    }}
    .summary {{
      font-size: 1rem;
      color: #c8cfc4;
      margin-bottom: 2rem;
      padding-bottom: 1.5rem;
      border-bottom: 1px solid rgba(122,171,110,0.15);
    }}
    section {{ margin-bottom: 1.75rem; }}
    h2 {{
      font-size: 0.75rem;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: #7aab6e;
      margin-bottom: 0.6rem;
    }}
    p {{ font-size: 0.95rem; }}
    ul {{
      padding-left: 1.2rem;
      font-size: 0.95rem;
    }}
    li {{ margin-bottom: 0.35rem; }}
    .meta-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.75rem 1.5rem;
      font-size: 0.9rem;
      margin-bottom: 2.5rem;
    }}
    .meta-item span:first-child {{
      display: block;
      font-size: 0.68rem;
      letter-spacing: 0.15em;
      text-transform: uppercase;
      color: #7aab6e;
      margin-bottom: 0.15rem;
    }}
    a {{ color: #7aab6e; word-break: break-all; }}
    .dss-tag {{
      display: inline-block;
      margin-top: 2.5rem;
      font-size: 0.68rem;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      color: rgba(122,171,110,0.45);
    }}
  </style>
</head>
<body>
  <p class="label">DSS — The Department of Species Services</p>
  <h1>{job.get('title', '')}</h1>

  <div class="summary">{job.get('short_summary', '')}</div>

  <div class="meta-grid">
    <div class="meta-item">
      <span>Employment</span>
      <span>{job.get('employment_status', '—')}</span>
    </div>
    <div class="meta-item">
      <span>Salary</span>
      <span>{job.get('salary_range', '—')}</span>
    </div>
    <div class="meta-item">
      <span>Location</span>
      <span>{job.get('location', '—')}</span>
    </div>
    <div class="meta-item">
      <span>Duration</span>
      <span>{job.get('duration', '—')}</span>
    </div>
  </div>

  {"<section><h2>Responsibilities</h2><ul>" + responsibilities_html + "</ul></section>" if responsibilities_html else ""}
  {"<section><h2>Qualifications</h2><ul>" + qualifications_html + "</ul></section>" if qualifications_html else ""}
  {"<section><h2>Benefits</h2><ul>" + benefits_html + "</ul></section>" if benefits_html else ""}
  {"<section><h2>Ecological Context & System Conditions</h2><p>" + job.get('summary', '') + "</p></section>" if job.get('summary') else ""}
  {"<section><h2>References</h2><ul>" + references_html + "</ul></section>" if references_html else ""}

  <span class="dss-tag">The Department of Species Services</span>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/api/health")
def health():
    return {"status": "ok"}
