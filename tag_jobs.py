"""
Tag all jobs in the database using the 5-question taxonomy.

For each job, the LLM assigns one or more tags per question based on
the job's title, summary, and responsibilities.

Tag vocabulary (matches App.jsx QUESTIONS):
  Q1 lifeSystems        : plants | animals | environmental systems
  Q2 habitatDomain      : land | water | air
  Q3 circadianPhase     : day | night
  Q4 operationalSetting : indoor | field work
  Q5 interactionMode    : observe | help | touch

Usage:
    python tag_jobs.py                           # tags all untagged jobs
    python tag_jobs.py --all                     # re-tags every job (overwrites existing tags)
    python tag_jobs.py --all --batch-size 1      # one API call per job
    python tag_jobs.py --dry-run-job-id 281      # print one-job prompt/input/output (no DB write)
"""

import argparse
import json
import os
import time

from openai import OpenAI

import db as _db

# ---------------------------------------------------------------------------
# API client (same config as main.py)
# ---------------------------------------------------------------------------
BASE_URL = os.getenv("OHMYGPT_BASE_URL", "https://api.ohmygpt.com/v1")
API_KEY  = os.getenv("OHMYGPT_API_KEY",  "sk-")
MODEL    = os.getenv("OHMYGPT_MODEL",    "gpt-5.4")

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

# ---------------------------------------------------------------------------
# Tag taxonomy
# ---------------------------------------------------------------------------
TAXONOMY = {
    "lifeSystems":        ["plants", "animals", "environmental systems"],
    "habitatDomain":      ["land", "water", "air"],
    "circadianPhase":     ["day", "night"],
    "operationalSetting": ["indoor", "field work"],
    "interactionMode":    ["observe", "help", "touch"],
}

TAXONOMY_GUIDANCE = """\
1. Life Systems — Which living systems draw your attention?
   • plants                 → work centred on plants, vegetation, forests, algae, fungi
   • animals                → work centred on animals (vertebrates, invertebrates, insects, fish, birds, mammals)
   • environmental systems  → work centred on water quality, air, soil, climate, nutrient cycles,
                              or cross-cutting ecosystem processes with no single dominant organism group

2. Habitat Domain — Where does your attention tend to stabilize?
   • land  → terrestrial habitats/ecosystems (forests, grasslands, wetlands, soil, urban green space)
   • water → aquatic habitats/ecosystems (freshwater, marine, coastal: rivers, streams, lakes, ponds, ocean)
   • air   → atmospheric/aerial domain (air quality, airborne monitoring, atmospheric processes)
   Note: this is about the target habitat/ecosystem being worked on, not whether the role is indoor vs field.

3. Circadian Phase — When is your perception most reliable?
   • day   → primarily daytime activity (diurnal surveys, classroom education, office analysis)
   • night → primarily nocturnal or crepuscular activity (night surveys, bat monitoring,
             owl counts, nocturnal species work) — also assign this if the job explicitly
             involves night-time fieldwork alongside daytime work

4. Operational Setting — Where do you maintain optimal function?
   • indoor     → primarily indoors or office-based (data analysis, education, coordination, lab work)
   • field work → primarily outdoors / field-based (surveys, restoration, field monitoring, direct
                  habitat intervention)
   Note: many jobs combine both; assign both if genuinely mixed.

5. Interaction Mode — How do you approach other species?
   • observe → primarily observe, monitor, survey, count, photograph — minimal direct interaction
   • help    → actively help, restore, rehabilitate, manage, or improve conditions for species
   • touch   → direct hands-on physical interaction (capture, handling, tagging, veterinary care,
               transplanting, seeding, physical removal of invasives)
"""

SYSTEM_PROMPT = f"""\
You are an ecology job classifier. For each job given to you, assign tags from the
taxonomy below. A job may receive multiple tags per dimension when genuinely warranted.

{TAXONOMY_GUIDANCE}

Return a JSON array — one object per job, in the same order — with this shape:
[
  {{
    "id": <job_id>,
    "tags": ["plants", "land", "day", "field work", "observe"]
  }},
  ...
]

Rules:
- Every job must have at least one tag per dimension (5 dimensions × ≥1 tag each → minimum 5 tags).
- Only use the exact tag strings listed above (case-sensitive).
- Do not include any explanation; return only the JSON array.
"""


def _build_job_text(job: dict) -> str:
    """Full text representation for tagging (includes all user-visible job details)."""
    parts = [
        f"ID: {job['id']}",
        f"Title: {job.get('title', '')}",
        f"Short Summary: {job.get('short_summary', '')}",
        f"Employment Status: {job.get('employment_status', '')}",
        f"Salary Range: {job.get('salary_range', '')}",
        f"Location: {job.get('location', '')}",
        f"Duration: {job.get('duration', '')}",
        f"Summary: {job.get('summary', '')}",
    ]

    resp = job.get("responsibilities", [])
    if resp:
        parts.append("Responsibilities:\n" + "\n".join(f"- {r}" for r in resp))

    quals = job.get("qualifications", [])
    if quals:
        parts.append("Qualifications:\n" + "\n".join(f"- {q}" for q in quals))

    benefits = job.get("benefits", [])
    if benefits:
        parts.append("Benefits:\n" + "\n".join(f"- {b}" for b in benefits))

    refs = job.get("references", [])
    if refs:
        parts.append("References:\n" + "\n".join(f"- {r}" for r in refs))

    return "\n".join(parts)


def _parse_llm_json(raw: str) -> list[dict]:
    """Parse LLM JSON response, tolerating markdown code fences."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def tag_batch(jobs: list[dict]) -> list[dict]:
    """Call the LLM to tag a batch of jobs. Returns list of {id, tags}."""
    user_content = "\n\n---\n\n".join(_build_job_text(j) for j in jobs)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_content},
        ],
    )
    raw = response.choices[0].message.content.strip()
    return _parse_llm_json(raw)


def run(retag_all: bool = False, batch_size: int = 5):
    _db.init_db()
    all_jobs = _db.get_all_jobs()

    if retag_all:
        to_tag = all_jobs
    else:
        to_tag = [j for j in all_jobs if not j.get("tags")]

    if not to_tag:
        print("All jobs already have tags. Use --all to re-tag.")
        return

    print(f"Tagging {len(to_tag)} job(s) in batches of {batch_size}...")

    total_tagged = 0
    for i in range(0, len(to_tag), batch_size):
        batch = to_tag[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(to_tag) + batch_size - 1) // batch_size
        print(f"  Batch {batch_num}/{total_batches} (jobs {i+1}–{min(i+batch_size, len(to_tag))})...", end=" ", flush=True)

        try:
            results = tag_batch(batch)
        except Exception as e:
            print(f"ERROR: {e}")
            print("  Retrying after 5 s...")
            time.sleep(5)
            try:
                results = tag_batch(batch)
            except Exception as e2:
                print(f"  Failed again: {e2}. Skipping batch.")
                continue

        # Save tags to DB
        for item in results:
            job_id = item.get("id")
            tags   = item.get("tags", [])
            _db.tag_jobs([job_id], tags)
            total_tagged += 1

        print(f"done ({len(results)} tagged)")

    print(f"\nFinished. {total_tagged} job(s) tagged.")


def dry_run_job(job_id: int):
    """Test-run a single job: print LLM input/output without writing DB."""
    _db.init_db()
    job = _db.get_job_by_id(job_id)
    if not job:
        print(f"Job {job_id} not found.")
        return

    user_content = _build_job_text(job)

    print("=== SYSTEM PROMPT ===")
    print(SYSTEM_PROMPT)
    print("\n=== USER CONTENT ===")
    print(user_content)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    raw = response.choices[0].message.content.strip()

    print("\n=== RAW MODEL OUTPUT ===")
    print(raw)

    try:
        parsed = _parse_llm_json(raw)
        print("\n=== PARSED JSON ===")
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"\nFailed to parse JSON output: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tag DSS jobs with the 5-question taxonomy.")
    parser.add_argument("--all", action="store_true", help="Re-tag all jobs, including already-tagged ones.")
    parser.add_argument("--batch-size", type=int, default=5, help="Jobs per API call (default 5).")
    parser.add_argument(
        "--dry-run-job-id",
        type=int,
        help="Test one job only: print prompt/input/output and do NOT write tags to DB.",
    )
    args = parser.parse_args()

    if args.dry_run_job_id is not None:
        dry_run_job(args.dry_run_job_id)
    else:
        run(retag_all=args.all, batch_size=args.batch_size)
