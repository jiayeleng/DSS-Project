"""
Step 1 result cache — backs up NewsAndSearchAgent output to local JSON files.

Cache key  : MD5 of the news URL
Cache dir  : .cache/step1/
Cache entry: {
    "url":        str,
    "cached_at":  str (ISO-8601),
    "nas_text":   str,          # raw final_output from NewsAndSearchAgent
    "chunks":     list[dict],   # snapshot of _EVIDENCE_CHUNKS after Step 1
}
"""

import hashlib
import json
import os
from datetime import datetime, timezone

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "step1")


def _path(news_url: str) -> str:
    url_hash = hashlib.md5(news_url.encode()).hexdigest()
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{url_hash}.json")


def load(news_url: str) -> dict | None:
    """Return the cached Step 1 payload, or None if not cached."""
    path = _path(news_url)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"  [Cache] Step 1 hit — loaded {len(data.get('chunks', []))} chunks from {path}")
        return data
    except Exception as e:
        print(f"  [Cache] Failed to load cache ({e}); will re-run Step 1.")
        return None


def save(news_url: str, nas_text: str, chunks: list[dict]) -> None:
    """Persist Step 1 output so the next run can skip the agent call."""
    path = _path(news_url)
    payload = {
        "url":       news_url,
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "nas_text":  nas_text,
        "chunks":    chunks,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"  [Cache] Step 1 saved → {path} ({len(chunks)} chunks)")
