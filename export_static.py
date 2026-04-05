"""
Export all jobs from jobs.db as self-contained static HTML files.

Usage:
    python export_static.py [--out-dir OUTPUT_DIR]

Default output: output/static/
Files are written as  output/static/jobs/<id>.html

After exporting, upload the output/static/ folder to any static host:
  - Netlify Drop : drag the folder to app.netlify.com/drop
  - GitHub Pages : push to a gh-pages branch and set the Pages source

Then point the frontend QR codes at the public URL by adding one line to
frontend/.env.local:
    VITE_QR_BASE=https://your-site.netlify.app
"""

import argparse
import os
import re

import db


# ---------------------------------------------------------------------------
# HTML rendering  (kept in sync with the template in server.py)
# ---------------------------------------------------------------------------

def _list_items(items):
    if not items:
        return ""
    return "".join(f"<li>{item}</li>" for item in items)


def _refs(items):
    if not items:
        return ""
    parts = []
    for ref in items:
        ref_linked = re.sub(
            r'(https?://\S+)',
            r'<a href="\1" target="_blank">\1</a>',
            ref,
        )
        parts.append(f"<li>{ref_linked}</li>")
    return "".join(parts)


def render_job_html(job: dict) -> str:
    responsibilities_html = _list_items(job.get("responsibilities", []))
    qualifications_html   = _list_items(job.get("qualifications", []))
    benefits_html         = _list_items(job.get("benefits", []))
    references_html       = _refs(job.get("references", []))
    em = "\u2014"

    return f"""<!DOCTYPE html>
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
      <span>{job.get('employment_status', em)}</span>
    </div>
    <div class="meta-item">
      <span>Salary</span>
      <span>{job.get('salary_range', em)}</span>
    </div>
    <div class="meta-item">
      <span>Location</span>
      <span>{job.get('location', em)}</span>
    </div>
    <div class="meta-item">
      <span>Duration</span>
      <span>{job.get('duration', em)}</span>
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


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export(out_dir: str) -> None:
    db.init_db()
    jobs = db.get_all_jobs()
    if not jobs:
        print("No jobs found in database.")
        return

    jobs_dir = os.path.join(out_dir, "jobs")
    os.makedirs(jobs_dir, exist_ok=True)

    for job in jobs:
        job_id = job["id"]
        path = os.path.join(jobs_dir, f"{job_id}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_job_html(job))
        print(f"  {path}")

    print(f"\n{len(jobs)} file(s) exported to {out_dir}/")
    print("\nNext steps:")
    print("  1. Upload the folder to a static host, e.g.:")
    print("       Netlify Drop  →  drag & drop at app.netlify.com/drop")
    print("       GitHub Pages  →  push to a gh-pages branch")
    print("  2. Add one line to frontend/.env.local:")
    print("       VITE_QR_BASE=https://your-site.netlify.app")
    print("  3. Restart the frontend dev server (npm run dev).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export jobs as static HTML")
    parser.add_argument(
        "--out-dir", default="output/static",
        help="Output directory (default: output/static)",
    )
    args = parser.parse_args()
    export(args.out_dir)
