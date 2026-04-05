"""
Generate images for jobs using Gemini 3.1 Flash via OhMyGPT proxy.

Usage:
    python generate_images.py [--job-ids 1 2 3]  # test specific jobs
    python generate_images.py --all               # generate for all jobs
"""

import argparse
import os
from pathlib import Path
import requests
import base64

import db as _db

# API configuration
OHMYGPT_BASE_URL = os.getenv("OHMYGPT_BASE_URL", "https://api.ohmygpt.com/v1")
OHMYGPT_API_KEY = os.getenv("OHMYGPT_API_KEY", "sk-")

# Output directory
OUTPUT_DIR = Path(__file__).parent / "frontend" / "public" / "images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_image(job: dict) -> bytes:
    """Generate an image using Gemini 3.1 Flash via OhMyGPT, passing job data directly."""
    title = job.get("title", "")
    summary = job.get("summary", "")
    responsibilities = job.get("responsibilities", [])
    references = job.get("references", [])

    job_text = f"""Generate a vivid, scientifically-grounded SQUARE image (1:1 aspect ratio) for this ecological job:

Job Title: {title}

Summary: {summary}

Responsibilities:
{chr(10).join(f"- {r}" for r in responsibilities[:3])}

References:
{chr(10).join(references[:2])}

Create an image that depicts the ecological work/species/habitat involved, showing the job in action (field work, monitoring, restoration, etc.). Make it visually compelling and realistic. IMPORTANT: The image must be square (equal width and height)."""

    payload = {
        "model": "gemini-3.1-flash-image-preview",
        "messages": [{"role": "user", "content": job_text}]
    }

    response = requests.post(
        f"{OHMYGPT_BASE_URL}/chat/completions",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OHMYGPT_API_KEY}",
        }
    )
    response.raise_for_status()

    data = response.json()
    if "choices" not in data or len(data["choices"]) == 0:
        raise ValueError(f"No image data in response: {data}")

    content = data["choices"][0].get("message", {}).get("content", "")

    # Handle list of parts (multimodal)
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                img_url = part["image_url"]["url"]
                if img_url.startswith("data:"):
                    b64 = img_url.split(",", 1)[1]
                    return base64.b64decode(b64)
                else:
                    return requests.get(img_url).content

    # Handle string URL
    if isinstance(content, str) and content.startswith("http"):
        return requests.get(content).content

    # Handle data URI or base64
    if isinstance(content, str):
        if content.startswith("data:"):
            b64 = content.split(",", 1)[1]
        else:
            b64 = content
        img_bytes = base64.b64decode(b64)

        # Find PNG signature and strip any prefix
        png_sig = b'\x89PNG\r\n\x1a\n'
        idx = img_bytes.find(png_sig)
        if idx > 0:
            img_bytes = img_bytes[idx:]

        return img_bytes

    raise ValueError(f"No image data in response: {data}")


def run(job_ids: list[int] = None, skip_existing: bool = False):
    _db.init_db()
    all_jobs = _db.get_all_jobs()

    if job_ids:
        jobs_to_process = [j for j in all_jobs if j["id"] in job_ids]
    else:
        jobs_to_process = all_jobs

    for i, job in enumerate(jobs_to_process, 1):
        job_id = job["id"]
        title = job.get("title", "")[:60]
        output_path = OUTPUT_DIR / f"{job_id}.png"

        if skip_existing and output_path.exists():
            print(f"[{i}/{len(jobs_to_process)}] Job {job_id}: {title} (skipped)")
            continue

        print(f"[{i}/{len(jobs_to_process)}] Job {job_id}: {title}")

        try:
            print(f"  → Generating image with Gemini 3.1...", end=" ", flush=True)
            image_bytes = generate_image(job)
            print("done")

            with open(output_path, "wb") as f:
                f.write(image_bytes)
            print(f"  ✓ Saved to {output_path}\n")

        except Exception as e:
            print(f"  ✗ ERROR: {e}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate images for jobs using Gemini 3.1")
    parser.add_argument(
        "--job-ids",
        type=int,
        nargs="+",
        help="Specific job IDs to process (for testing)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate for all jobs (default: first 5 for testing)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip jobs that already have generated images",
    )
    args = parser.parse_args()

    if args.all:
        run(skip_existing=args.skip_existing)
    elif args.job_ids:
        run(args.job_ids, skip_existing=args.skip_existing)
    else:
        # Default: test first 5 jobs
        all_jobs = _db.get_all_jobs()
        test_ids = [j["id"] for j in all_jobs[:5]]
        print(f"Testing with first 5 jobs: {test_ids}\n")
        run(test_ids, skip_existing=args.skip_existing)
