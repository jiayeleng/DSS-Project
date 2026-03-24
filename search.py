"""
Web search and scraping utility functions used as tools by the multi-agent system.

Scraping pipeline per URL
--------------------------
1. HEAD request → detect Content-Type (HTML vs PDF)

HTML path:
  a. GET → trafilatura.extract()  (primary)
  b. fallback → readability-lxml Article
  c. if result < 800 chars (likely JS-rendered) → playwright render → repeat a/b

PDF path:
  a. Download to local cache (named by URL hash)
  b. PyMuPDF (fitz) page.get_text("text") per page
  c. If total extracted text < 800 chars → mark extraction_warning, return early

Chunking:
  HTML  → paragraph-based chunks, target ~1500 chars, 1-2 paragraph overlap
  PDF   → page-based chunks (one chunk per page or split long pages by paragraph)

Each chunk carries metadata:
  url, title, doc_id, section, chunk_index, chunk_id
"""

import hashlib
import json
import os
import re
import tempfile
from typing import Optional

import requests
from bs4 import BeautifulSoup
from serpapi import GoogleSearch

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SERPAPI_API_KEY = "b5aac9386844457245fccb95ef4adb2d372ec3964e82d7cb3160140e084c27fe"#"8e60264049ce719c653369f63749ed932a78f534a33a914bcc2cc60651725ccf"#"98c9d1b4c1a7790ee01b26c7ba470b02920692924a0a2b0ac0109e0169ae31a1"
PDF_CACHE_DIR = os.path.join(tempfile.gettempdir(), "dss_pdf_cache")
os.makedirs(PDF_CACHE_DIR, exist_ok=True)

TARGET_CHUNK_CHARS = 4000   # target size per chunk (~1000 tokens)
MAX_CHUNK_CHARS = 5000      # hard ceiling — no chunk may exceed this
MIN_CONTENT_CHARS = 800
OVERLAP_CHARS = 250         # overlap between consecutive chunks


# ---------------------------------------------------------------------------
# Google Search
# ---------------------------------------------------------------------------

def google_search(query: str, num_results: int = 5) -> list[dict]:
    """
    Search the web using SerpApi Google Search.
    Returns a list of results with title, link, and snippet.
    """
    params = {
        "engine": "google",
        "q": query,
        "num": num_results,
        "api_key": SERPAPI_API_KEY,
        "location": "California, United States",
        "hl": "en",
        "gl": "us",
    }
    results = GoogleSearch(params).get_dict()

    output = []
    for item in results.get("organic_results", []):
        output.append({
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "snippet": item.get("snippet", ""),
        })
    return output


# ---------------------------------------------------------------------------
# Content-type detection
# ---------------------------------------------------------------------------

def _is_pdf_url(url: str, headers: dict) -> bool:
    """Return True if the URL points to a PDF (by Content-Type or extension)."""
    ct = headers.get("Content-Type", "").lower()
    return "pdf" in ct or url.lower().split("?")[0].endswith(".pdf")


# ---------------------------------------------------------------------------
# HTML extraction
# ---------------------------------------------------------------------------

def _extract_html(html: str) -> str:
    """Extract main text from HTML via trafilatura → readability fallback."""
    text = ""

    # Primary: trafilatura
    try:
        import trafilatura
        text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
    except Exception:
        pass

    # Fallback: readability-lxml
    if not text and html and html.strip():
        try:
            import io
            import sys
            from readability import Document
            # Suppress readability's stderr noise (e.g. "error getting summary")
            _stderr = sys.stderr
            sys.stderr = io.StringIO()
            try:
                doc = Document(html)
                summary = doc.summary()
            finally:
                sys.stderr = _stderr
            soup = BeautifulSoup(summary, "html.parser")
            text = soup.get_text(separator="\n", strip=True)
        except BaseException:
            # Catch BaseException to also handle lxml.etree.ParserError
            # which may not inherit from Exception in all lxml builds
            pass

    # Last resort: simple BeautifulSoup
    if not text:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
            tag.decompose()
        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_=re.compile(r"content|main|article", re.I))
        )
        text = (main or soup).get_text(separator="\n", strip=True)

    return text


def _extract_html_with_playwright(url: str) -> str:
    """Render a JS-heavy page with Playwright and return extracted text."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=20000, wait_until="networkidle")
            html = page.content()
            browser.close()
        return _extract_html(html)
    except Exception as e:
        return ""


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def _pdf_cache_path(url: str) -> str:
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return os.path.join(PDF_CACHE_DIR, f"{url_hash}.pdf")


def _download_pdf(url: str) -> Optional[str]:
    """Download PDF to local cache and return the file path, or None on failure."""
    cache_path = _pdf_cache_path(url)
    if os.path.exists(cache_path):
        return cache_path
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        with open(cache_path, "wb") as f:
            f.write(resp.content)
        return cache_path
    except Exception:
        return None


def _extract_pdf(pdf_path: str) -> tuple[list[dict], Optional[str]]:
    """
    Extract text from a PDF using PyMuPDF.
    Returns (pages, extraction_warning).
    Each page: {"page_num": int, "text": str}
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        pages = []
        for i, page in enumerate(doc, start=1):
            raw = page.get_text("text")
            # Clean: collapse excessive blank lines
            lines = [ln.strip() for ln in raw.split("\n")]
            cleaned = "\n".join(ln for ln in lines if ln)
            pages.append({"page_num": i, "text": cleaned})
        doc.close()

        total_text = "".join(p["text"] for p in pages)
        warning = None
        if len(total_text) < MIN_CONTENT_CHARS:
            warning = "low_text_pdf_maybe_scanned"

        return pages, warning
    except Exception as e:
        return [], f"pdf_extraction_error: {e}"


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _overlap_paras(paras: list[str]) -> list[str]:
    """Return the trailing paragraphs that together fit within OVERLAP_CHARS."""
    overlap: list[str] = []
    total = 0
    for para in reversed(paras):
        if total + len(para) > OVERLAP_CHARS and overlap:
            break
        overlap.insert(0, para)
        total += len(para)
    return overlap


def _split_long_para(para: str, max_chars: int) -> list[str]:
    """Split a single paragraph that exceeds max_chars at sentence boundaries."""
    if len(para) <= max_chars:
        return [para]
    # Split on sentence-ending punctuation followed by a space
    sentences = re.split(r'(?<=[.!?])\s+', para)
    parts: list[str] = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) + 1 > max_chars and current:
            parts.append(current.strip())
            current = sent
        else:
            current = (current + " " + sent).strip() if current else sent
    if current:
        parts.append(current.strip())
    # Final safety: hard-truncate any part still over the limit
    return [p[:max_chars] for p in parts]


def _chunk_html_text(text: str, url: str, title: str, doc_id: str) -> list[dict]:
    """Split HTML text into overlapping paragraph-based chunks."""
    raw_paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    # Pre-split any paragraph that is itself too long
    paragraphs: list[str] = []
    for para in raw_paragraphs:
        paragraphs.extend(_split_long_para(para, MAX_CHUNK_CHARS))

    def _emit_chunk(paras: list[str], idx: int) -> dict:
        chunk_text = "\n\n".join(paras)[:MAX_CHUNK_CHARS]
        chunk_id = hashlib.md5(f"{doc_id}:{idx}".encode()).hexdigest()[:12]
        return {
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "url": url,
            "title": title,
            "section": f"chunk-{idx + 1}",
            "chunk_index": idx,
            "text": chunk_text,
        }

    chunks = []
    current_paras: list[str] = []
    current_len = 0
    chunk_index = 0

    for para in paragraphs:
        # If adding this paragraph would exceed the hard ceiling, flush first
        if current_paras and current_len + len(para) > MAX_CHUNK_CHARS:
            chunks.append(_emit_chunk(current_paras, chunk_index))
            current_paras = _overlap_paras(current_paras)
            current_len = sum(len(p) for p in current_paras)
            chunk_index += 1

        current_paras.append(para)
        current_len += len(para)

        if current_len >= TARGET_CHUNK_CHARS:
            chunks.append(_emit_chunk(current_paras, chunk_index))
            current_paras = _overlap_paras(current_paras)
            current_len = sum(len(p) for p in current_paras)
            chunk_index += 1

    # Flush remaining
    if current_paras:
        chunks.append(_emit_chunk(current_paras, chunk_index))

    return chunks


def _chunk_pdf_pages(pages: list[dict], url: str, title: str, doc_id: str) -> list[dict]:
    """
    Chunk PDF pages: one chunk per page; split long pages by paragraph.
    """
    chunks = []
    chunk_index = 0

    for page in pages:
        page_num = page["page_num"]
        page_text = page["text"]
        if not page_text.strip():
            continue

        if len(page_text) <= TARGET_CHUNK_CHARS:
            chunk_id = hashlib.md5(f"{doc_id}:p{page_num}".encode()).hexdigest()[:12]
            chunks.append({
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "url": url,
                "title": title,
                "section": f"Page {page_num}",
                "chunk_index": chunk_index,
                "text": page_text[:MAX_CHUNK_CHARS],
            })
            chunk_index += 1
        else:
            # Long page: pre-split paragraphs then chunk with hard ceiling
            raw_paras = [p.strip() for p in re.split(r"\n{2,}", page_text) if p.strip()]
            paragraphs: list[str] = []
            for para in raw_paras:
                paragraphs.extend(_split_long_para(para, MAX_CHUNK_CHARS))

            current_paras: list[str] = []
            current_len = 0
            sub = 0

            for para in paragraphs:
                if current_paras and current_len + len(para) > MAX_CHUNK_CHARS:
                    chunk_text = "\n\n".join(current_paras)[:MAX_CHUNK_CHARS]
                    section = f"Page {page_num}" if sub == 0 else f"Page {page_num}-{sub + 1}"
                    chunk_id = hashlib.md5(f"{doc_id}:p{page_num}:{sub}".encode()).hexdigest()[:12]
                    chunks.append({
                        "chunk_id": chunk_id, "doc_id": doc_id, "url": url,
                        "title": title, "section": section,
                        "chunk_index": chunk_index, "text": chunk_text,
                    })
                    current_paras = _overlap_paras(current_paras)
                    current_len = sum(len(p) for p in current_paras)
                    chunk_index += 1
                    sub += 1

                current_paras.append(para)
                current_len += len(para)

                if current_len >= TARGET_CHUNK_CHARS:
                    chunk_text = "\n\n".join(current_paras)[:MAX_CHUNK_CHARS]
                    section = f"Page {page_num}" if sub == 0 else f"Page {page_num}-{sub + 1}"
                    chunk_id = hashlib.md5(f"{doc_id}:p{page_num}:{sub}".encode()).hexdigest()[:12]
                    chunks.append({
                        "chunk_id": chunk_id, "doc_id": doc_id, "url": url,
                        "title": title, "section": section,
                        "chunk_index": chunk_index, "text": chunk_text,
                    })
                    current_paras = _overlap_paras(current_paras)
                    current_len = sum(len(p) for p in current_paras)
                    chunk_index += 1
                    sub += 1

            if current_paras:
                chunk_text = "\n\n".join(current_paras)[:MAX_CHUNK_CHARS]
                chunk_id = hashlib.md5(f"{doc_id}:p{page_num}:{sub}".encode()).hexdigest()[:12]
                chunks.append({
                    "chunk_id": chunk_id, "doc_id": doc_id, "url": url,
                    "title": title, "section": f"Page {page_num}",
                    "chunk_index": chunk_index, "text": chunk_text,
                })
                chunk_index += 1

    return chunks


# ---------------------------------------------------------------------------
# Main scrape entry point
# ---------------------------------------------------------------------------

def scrape_webpage(url: str, max_chars: int = 8000) -> dict:
    """
    Scrape a URL and return cleaned text content (up to max_chars) plus chunks.

    Returns:
    {
        "url": str,
        "title": str,
        "content": str,           # full joined text, truncated to max_chars
        "chunks": list[dict],     # structured chunks with metadata
        "success": bool,
        "extraction_warning": str | None,
        "error": str | None,
    }
    """
    extraction_warning = None
    title = ""

    # ------------------------------------------------------------------
    # Step 1: HEAD to detect content type
    # ------------------------------------------------------------------
    try:
        head_resp = requests.head(url, timeout=10, allow_redirects=True,
                                  headers={"User-Agent": "Mozilla/5.0"})
        is_pdf = _is_pdf_url(url, dict(head_resp.headers))
    except Exception:
        is_pdf = url.lower().split("?")[0].endswith(".pdf")

    doc_id = hashlib.md5(url.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # PDF path
    # ------------------------------------------------------------------
    if is_pdf:
        pdf_path = _download_pdf(url)
        if not pdf_path:
            return {"url": url, "title": title, "content": "", "chunks": [],
                    "success": False, "extraction_warning": None,
                    "error": "Failed to download PDF"}

        pages, warning = _extract_pdf(pdf_path)
        extraction_warning = warning

        if warning and "low_text" in str(warning):
            return {"url": url, "title": title, "content": "", "chunks": [],
                    "success": False, "extraction_warning": extraction_warning,
                    "error": None}

        full_text = "\n\n".join(
            f"[Page {p['page_num']}]\n{p['text']}" for p in pages
        )
        chunks = _chunk_pdf_pages(pages, url=url, title=url, doc_id=doc_id)
        content = full_text[:max_chars]
        return {"url": url, "title": url, "content": content, "chunks": chunks,
                "success": bool(content), "extraction_warning": extraction_warning,
                "error": None}

    # ------------------------------------------------------------------
    # HTML path
    # ------------------------------------------------------------------
    try:
        resp = requests.get(url, timeout=15,
                            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return {"url": url, "title": title, "content": "", "chunks": [],
                "success": False, "extraction_warning": None, "error": str(e)}

    # Extract title
    try:
        soup_title = BeautifulSoup(html, "html.parser")
        title = (soup_title.find("title") or soup_title.find("h1") or object()
                 ).get_text(strip=True) if soup_title.find("title") else url
    except Exception:
        title = url

    text = _extract_html(html)

    # Playwright fallback for JS-rendered pages
    if len(text) < MIN_CONTENT_CHARS:
        extraction_warning = "short_content_tried_playwright"
        rendered = _extract_html_with_playwright(url)
        if len(rendered) > len(text):
            text = rendered

    if len(text) < MIN_CONTENT_CHARS and not text.strip():
        return {"url": url, "title": title, "content": "", "chunks": [],
                "success": False,
                "extraction_warning": extraction_warning or "insufficient_content",
                "error": None}

    chunks = _chunk_html_text(text, url=url, title=title, doc_id=doc_id)
    content = text[:max_chars]

    return {"url": url, "title": title, "content": content, "chunks": chunks,
            "success": True, "extraction_warning": extraction_warning, "error": None}


# ---------------------------------------------------------------------------
# Lightweight single-query search (no scraping)
# ---------------------------------------------------------------------------

def search_and_filter(query: str, num_results: int = 5) -> list[dict]:
    """
    Search Google for a single query and return deduplicated candidate results.
    Does NOT scrape — returns title, url, snippet only for the agent to decide
    which URLs are worth scraping.
    """
    try:
        results = google_search(query, num_results=num_results)
    except Exception as e:
        return [{"error": str(e)}]

    seen: set[str] = set()
    out = []
    for r in results:
        url = r.get("link", "").strip()
        if url and url not in seen:
            seen.add(url)
            out.append({
                "title": r.get("title", ""),
                "url": url,
                "snippet": r.get("snippet", ""),
            })
    return out


def scrape_and_chunk(url: str) -> dict:
    """
    Scrape a single URL and return its chunks with metadata.
    Returns:
    {
        "success": bool,
        "url": str,
        "title": str,
        "chunks": list[dict],        # each chunk has text + metadata
        "extraction_warning": str | None,
        "error": str | None,
    }
    """
    result = scrape_webpage(url, max_chars=50000)
    return {
        "success": result["success"],
        "url": result["url"],
        "title": result.get("title", ""),
        "chunks": result.get("chunks", []),
        "extraction_warning": result.get("extraction_warning"),
        "error": result.get("error"),
    }


# ---------------------------------------------------------------------------
# Embedding-based chunk retrieval (FAISS-backed)
# ---------------------------------------------------------------------------

EMBEDDING_MODEL = "text-embedding-3-small"


_EMBED_BATCH_SIZE = 20  # number of texts per embedding API call


def _embed_texts(texts: list[str], api_key: str, base_url: str) -> list[list[float]]:
    """Batch-call the embeddings API; return one vector per input text."""
    import time
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[i: i + _EMBED_BATCH_SIZE]
        for attempt in range(3):
            try:
                response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
                # response.data is sorted by index, so order is preserved
                batch_vecs = sorted(response.data, key=lambda d: d.index)
                all_embeddings.extend(d.embedding for d in batch_vecs)
                break
            except Exception as e:
                if attempt == 2:
                    raise
                wait = 2 ** attempt  # 1s, 2s
                print(f"  [Embedding] Attempt {attempt + 1} failed ({e}); retrying in {wait}s…")
                time.sleep(wait)
    return all_embeddings


class EmbeddingIndex:
    """
    Manages chunk embeddings with a FAISS IndexFlatIP index for fast similarity search.

    Vectors are L2-normalised before insertion so that inner-product search is
    equivalent to cosine similarity.  Falls back to linear scan if faiss is not
    installed.

    Usage:
        index = EmbeddingIndex()
        index.add(chunks, api_key, base_url)   # embed & insert new chunks
        results = index.search(query, top_k, api_key, base_url)
        index.reset()                           # clear for a new pipeline run
    """

    def __init__(self) -> None:
        self._chunk_ids: list[str] = []          # ordered list of chunk_ids in the index
        self._id_to_chunk: dict[str, dict] = {}  # chunk_id → chunk dict
        self._faiss_index = None                 # faiss.IndexFlatIP, built lazily
        self._dim: Optional[int] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_build_index(self, dim: int):
        """Return (or create) the FAISS index for the given embedding dimension."""
        try:
            import faiss  # type: ignore
        except ImportError:
            return None

        if self._faiss_index is None or self._dim != dim:
            self._faiss_index = faiss.IndexFlatIP(dim)
            self._dim = dim
        return self._faiss_index

    @staticmethod
    def _normalise(vec: list[float]) -> "list[float]":
        import math
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0:
            return vec
        return [x / norm for x in vec]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, chunks: list[dict], api_key: str, base_url: str) -> None:
        """Embed any chunks not yet in the index and add them."""
        import numpy as np

        new_chunks = [c for c in chunks if c.get("chunk_id", "") not in self._id_to_chunk]
        if not new_chunks:
            return

        texts = [c.get("text", "") for c in new_chunks]
        try:
            vectors = _embed_texts(texts, api_key=api_key, base_url=base_url)
        except Exception as e:
            print(f"  [Embedding] Failed to embed {len(new_chunks)} chunk(s): {e}")
            return

        normed = [self._normalise(v) for v in vectors]
        dim = len(normed[0])
        faiss_index = self._get_or_build_index(dim)

        valid_chunks = []
        valid_normed = []
        for chunk, vec in zip(new_chunks, normed):
            cid = chunk.get("chunk_id", "")
            if not cid:
                continue
            # Store vector alongside chunk so the linear-scan fallback can use it
            self._id_to_chunk[cid] = {**chunk, "_vec": vec}
            self._chunk_ids.append(cid)
            valid_chunks.append(chunk)
            valid_normed.append(vec)

        # Add all vectors to FAISS in a single batch call to avoid the
        # repeated small-array malloc/free cycle that crashes on macOS
        if faiss_index is not None and valid_normed:
            arr = np.array(valid_normed, dtype="float32")
            faiss_index.add(arr)

    def search(
        self,
        query: str,
        top_k: int,
        api_key: str,
        base_url: str,
    ) -> list[dict]:
        """Return top_k chunks most similar to query, with a 'similarity' field."""
        import numpy as np

        if not self._id_to_chunk:
            return []

        try:
            query_vec = _embed_texts([query], api_key=api_key, base_url=base_url)[0]
        except Exception as e:
            print(f"  [Embedding] Query embedding failed: {e}. Falling back to insertion order.")
            return [dict(c, similarity=0.0) for c in list(self._id_to_chunk.values())[:top_k]]

        query_normed = self._normalise(query_vec)
        k = min(top_k, len(self._chunk_ids))

        faiss_index = self._faiss_index
        if faiss_index is not None and faiss_index.ntotal > 0:
            # FAISS path: fast approximate nearest-neighbour search
            q_arr = np.array([query_normed], dtype="float32")
            scores, indices = faiss_index.search(q_arr, k)
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(self._chunk_ids):
                    continue
                cid = self._chunk_ids[idx]
                chunk = self._id_to_chunk.get(cid)
                if chunk:
                    results.append(dict(chunk, similarity=round(float(score), 4)))
            return results
        else:
            # Fallback: linear scan (faiss not installed or index empty)
            scored = []
            for cid, chunk in self._id_to_chunk.items():
                vec = chunk.get("_vec")
                if vec is None:
                    continue
                sim = sum(a * b for a, b in zip(query_normed, vec))
                scored.append((sim, chunk))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [dict(c, similarity=round(s, 4)) for s, c in scored[:k]]

    def reset(self) -> None:
        """Clear all state for a new pipeline run."""
        self._chunk_ids.clear()
        self._id_to_chunk.clear()
        self._faiss_index = None
        self._dim = None


# Module-level index instance shared across the pipeline run
_EMBEDDING_INDEX = EmbeddingIndex()

# Keep _CHUNK_EMBEDDING_CACHE as an alias so main.py's .clear() still works
_CHUNK_EMBEDDING_CACHE = _EMBEDDING_INDEX  # type: ignore[assignment]


def retrieve_chunks_embedding(
    query: str,
    chunks: list[dict],
    top_k: int = 10,
    api_key: str = "",
    base_url: str = "https://api.ohmygpt.com/v1",
) -> list[dict]:
    """
    Retrieve the most relevant chunks for a query using FAISS + OpenAI embeddings.

    New chunks are embedded and added to the FAISS index on first call;
    subsequent calls reuse the index.  Falls back to linear scan if faiss
    is not installed.

    Args:
        query:    Free-text query string.
        chunks:   List of chunk dicts (each must have "text" and "chunk_id" fields).
        top_k:    Number of top chunks to return.
        api_key:  OpenAI-compatible API key.
        base_url: API base URL.

    Returns:
        List of up to top_k chunk dicts sorted by cosine similarity (best first),
        each with an extra "similarity" field.
    """
    if not chunks:
        return []

    _EMBEDDING_INDEX.add(chunks, api_key=api_key, base_url=base_url)
    return _EMBEDDING_INDEX.search(query, top_k=top_k, api_key=api_key, base_url=base_url)


