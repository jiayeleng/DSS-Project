"""
Tag all jobs in the database using the 5-question taxonomy.

For each job, the LLM assigns one or more tags per question based on
the job's title, summary, and responsibilities.

Tag vocabulary (matches App.jsx QUESTIONS):
  Q1 livingSystem : Flora | Fauna | Atmosphere
  Q2 attention    : Ground | Current | Drift
  Q3 perception   : Under Sun | Under Moon
  Q4 function     : Shelter | Exposure
  Q5 approach     : Witness | Assist | Contact

Usage:
    python tag_jobs.py              # tags all untagged jobs
    python tag_jobs.py --all        # re-tags every job (overwrites existing tags)
"""

import argparse
import json
import os
import sys
import time

from openai import OpenAI

import db as _db

# ---------------------------------------------------------------------------
# API client (same config as main.py)
# ---------------------------------------------------------------------------
BASE_URL = os.getenv("OHMYGPT_BASE_URL", "https://api.ohmygpt.com/v1")
API_KEY  = os.getenv("OHMYGPT_API_KEY",  "sk-PnEpFe4EC11faBfeD38dT3BLbkFJa2c7116E710C47E3a7Cf")
MODEL    = os.getenv("OHMYGPT_MODEL",    "gpt-5-mini-2025-08-07")

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

# ---------------------------------------------------------------------------
# Tag taxonomy
# ---------------------------------------------------------------------------
TAXONOMY = {
    "livingSystem": ["Flora", "Fauna", "Atmosphere"],
    "attention":    ["Ground", "Current", "Drift"],
    "perception":   ["Under Sun", "Under Moon"],
    "function":     ["Shelter", "Exposure"],
    "approach":     ["Witness", "Assist", "Contact"],
}

TAXONOMY_GUIDANCE = """\
Tag taxonomy (choose one or more per dimension for each job):

1. livingSystem — Which living systems does this job primarily involve?
   • Flora      → work centred on plants, vegetation, forests, algae, fungi
   • Fauna      → work centred on animals (vertebrates, invertebrates, insects, fish, birds, mammals)
   • Atmosphere → work centred on environmental systems: water quality, air, soil, climate, nutrient cycles,
                  or cross-cutting ecosystem processes with no single dominant organism group

2. attention — Where does the work physically take place?
   • Ground → terrestrial environments (forests, grasslands, wetlands, soil, urban green space)
   • Current → aquatic / freshwater environments (rivers, streams, lakes, ponds)
   • Drift  → marine / coastal / atmospheric environments (ocean, coast, air monitoring)

3. perception — When does the core work activity happen?
   • Under Sun  → primarily daytime activity (diurnal surveys, classroom education, office analysis)
   • Under Moon → primarily nocturnal or crepuscular activity (night surveys, bat monitoring,
                  owl counts, nocturnal species work) — also assign this if the job explicitly
                  involves night-time fieldwork alongside daytime work

4. function — What is the primary working environment?
   • Shelter   → primarily indoors or office-based (data analysis, education, coordination, lab work)
   • Exposure  → primarily outdoors / field-based (surveys, restoration, field monitoring, direct
                 habitat intervention)
   Note: many jobs combine both; assign both if genuinely mixed.

5. approach — How does the person interact with other species?
   • Witness  → primarily observe, monitor, survey, count, photograph — minimal direct interaction
   • Assist   → actively help, restore, rehabilitate, manage, or improve conditions for species
   • Contact  → direct hands-on physical interaction (capture, handling, tagging, veterinary care,
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
    "tags": ["Flora", "Ground", "Under Sun", "Exposure", "Witness"]
  }},
  ...
]

Rules:
- Every job must have at least one tag per dimension (5 dimensions × ≥1 tag each → minimum 5 tags).
- Only use the exact tag strings listed above (case-sensitive).
- Do not include any explanation; return only the JSON array.
"""


def _build_job_text(job: dict) -> str:
    """Compact text representation of a job for the prompt."""
    parts = [
        f"ID: {job['id']}",
        f"Title: {job.get('title', '')}",
        f"Summary: {job.get('short_summary', '') or job.get('summary', '')[:300]}",
    ]
    resp = job.get("responsibilities", [])
    if resp:
        parts.append("Responsibilities: " + "; ".join(resp[:4]))
    quals = job.get("qualifications", [])
    if quals:
        parts.append("Qualifications: " + "; ".join(quals[:3]))
    loc = job.get("location", "")
    if loc:
        parts.append(f"Location: {loc}")
    return "\n".join(parts)


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

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tag DSS jobs with the 5-question taxonomy.")
    parser.add_argument("--all", action="store_true", help="Re-tag all jobs, including already-tagged ones.")
    parser.add_argument("--batch-size", type=int, default=5, help="Jobs per API call (default 5).")
    args = parser.parse_args()
    run(retag_all=args.all, batch_size=args.batch_size)
