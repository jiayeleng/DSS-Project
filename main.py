"""
Ecology News Multi-Agent System
================================
Pipeline:
  1. NewsAndSearchAgent  – Fetch a news URL, analyse ecological issues & root causes,
                           then iteratively search/scrape/filter the web until enough
                           high-quality evidence documents are collected.
  2. JobRecommendationAgent – Generate structured job recommendations from the evidence,
                           each with References.
  3. QualityCheckAgent   – Review each job recommendation; failed ones are sent back for
                           revision until all pass.

Usage:
    python main.py <news_url>
    # or import and call run_pipeline(news_url) directly.

Environment variables (all optional, defaults are set in code):
    OPENAI_API_KEY  – API key (defaults to the hardcoded key)
    OPENAI_BASE_URL – Proxy base URL (defaults to https://api.ohmygpt.com)
    OPENAI_MODEL    – Model name (defaults to gpt-4o)
"""

import asyncio
import io
import json
import os
import sys
from datetime import datetime

import db as _db
import cache as _cache
_db.init_db()

from openai import AsyncOpenAI
from agents import Agent, Runner, function_tool, set_default_openai_client, set_default_openai_api, set_tracing_disabled
from pydantic import BaseModel

from search import search_and_filter, scrape_and_chunk as _scrape_and_chunk, retrieve_chunks_embedding, _EMBEDDING_INDEX

# ---------------------------------------------------------------------------
# Client configuration
# ---------------------------------------------------------------------------
BASE_URL: str = os.getenv("OHMYGPT_BASE_URL", "https://api.ohmygpt.com/v1")
API_KEY: str = os.getenv("OHMYGPT_API_KEY", "sk-PnEpFe4EC11faBfeD38dT3BLbkFJa2c7116E710C47E3a7Cf")
MODEL: str = os.getenv("OHMYGPT_MODEL", "gpt-5-mini-2025-08-07")

# Configure the SDK to use the custom proxy client
_client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_default_openai_client(_client)
# ohmygpt exposes a Chat Completions-compatible endpoint
set_default_openai_api("chat_completions")
# Disable tracing (tracing requires a real OpenAI key)
set_tracing_disabled(True)

# ---------------------------------------------------------------------------
# Pydantic output schemas
# ---------------------------------------------------------------------------

class EvidenceDoc(BaseModel):
    """A single kept document from the NewsAndSearchAgent."""
    url: str
    title: str

class NewsAndSearchResult(BaseModel):
    """Output from the NewsAndSearchAgent."""
    ecological_issues: list[str]
    kept_docs: list[EvidenceDoc]   # title + url of all scraped-and-kept documents


class JobRecommendations(BaseModel):
    """Output from the JobRecommendationAgent."""
    jobs: list[dict]                      # full job details including per-job references
    all_references: list[str] = []        # deduplicated master reference list "[n] Title — URL"


class QualityCheckResult(BaseModel):
    """Output from the QualityCheckAgent — revised jobs ready for publication."""
    jobs: list[dict]   # minimally edited versions of the input jobs


# ---------------------------------------------------------------------------
# Global chunk store — populated by fetch_news & scrape_url, consumed by retrieve_evidence
# ---------------------------------------------------------------------------

_EVIDENCE_CHUNKS: list[dict] = []

# ---------------------------------------------------------------------------
# Tool definitions (wrapped for the Agents SDK)
# ---------------------------------------------------------------------------

@function_tool
def fetch_news(url: str) -> str:
    """
    Fetch a news article from the given URL and return its full text content.
    The article's chunks are also stored internally for later embedding retrieval.
    """
    result = _scrape_and_chunk(url)
    chunks = result.get("chunks", [])
    # Deduplicate by doc_id so re-fetching the same URL doesn't add duplicate chunks
    existing_doc_ids = {c.get("doc_id", "") for c in _EVIDENCE_CHUNKS}
    new_chunks = [c for c in chunks if c.get("doc_id", "") not in existing_doc_ids]
    _EVIDENCE_CHUNKS.extend(new_chunks)
    if not result["success"]:
        return f"Failed to fetch page: {result.get('error', 'unknown error')}"
    return result.get("content", "") or "\n".join(c.get("text", "") for c in chunks)


@function_tool
def search_web(query: str) -> str:
    """
    Search Google for the given query and return up to 10 candidate results as JSON.
    Each result has: title, url, snippet.
    Does NOT scrape — use scrape_url to retrieve content for selected URLs.
    """
    results = search_and_filter(query, num_results=10)
    return json.dumps(results, ensure_ascii=False, indent=2)


@function_tool
def scrape_url(url: str) -> str:
    """
    Scrape a single URL and return its extracted text content and chunks as JSON.
    Returns: {success, url, title, content_preview (first 500 chars), num_chunks,
              extraction_warning, error}
    The chunks are also stored internally for later embedding retrieval.
    PDF URLs are automatically skipped — only web pages are scraped.
    """
    # Skip PDFs — they are large, chunk poorly, and bias evidence retrieval
    if url.lower().split("?")[0].endswith(".pdf"):
        return json.dumps({
            "success": False,
            "url": url,
            "title": "",
            "content_preview": "",
            "num_chunks": 0,
            "extraction_warning": "pdf_skipped",
            "error": "PDF documents are excluded. Please use a different URL.",
        }, ensure_ascii=False, indent=2)

    result = _scrape_and_chunk(url)
    chunks = result.get("chunks", [])
    # Deduplicate by doc_id so scraping the same URL twice doesn't add duplicate chunks
    existing_doc_ids = {c.get("doc_id", "") for c in _EVIDENCE_CHUNKS}
    new_chunks = [c for c in chunks if c.get("doc_id", "") not in existing_doc_ids]
    _EVIDENCE_CHUNKS.extend(new_chunks)
    # Return a lightweight summary so the agent can judge relevance without
    # being overwhelmed by the full chunk content
    preview = ""
    if chunks:
        preview = chunks[0].get("text", "")[:500]
    return json.dumps({
        "success": result["success"],
        "url": result["url"],
        "title": result.get("title", ""),
        "content_preview": preview,
        "num_chunks": len(chunks),
        "extraction_warning": result.get("extraction_warning"),
        "error": result.get("error"),
    }, ensure_ascii=False, indent=2)


@function_tool
def retrieve_evidence(query: str) -> str:
    """
    Retrieve the top 10 most relevant evidence chunks for the given query using
    OpenAI embedding similarity (text-embedding-3-small).
    Use this to gather supporting evidence before writing each job recommendation.

    Input:  query – a short description of the job role or the ecological problem it addresses,
            e.g. "riparian habitat restoration invasive species removal"

    Output: JSON array of up to 10 chunks, each with:
            {chunk_id, url, title, section, text, similarity}
    """
    if not _EVIDENCE_CHUNKS:
        return json.dumps({"error": "No evidence chunks available. Run scrape_url first."})
    top_chunks = retrieve_chunks_embedding(
        query,
        _EVIDENCE_CHUNKS,
        top_k=10,
        api_key=API_KEY,
        base_url=BASE_URL,
    )
    slim = [
        {
            "chunk_id": c.get("chunk_id", ""),
            "url": c.get("url", ""),
            "title": c.get("title", ""),
            "section": c.get("section", ""),
            "text": c.get("text", "")[:1200],   # cap per chunk to avoid context overflow
            "similarity": c.get("similarity", 0.0),
        }
        for c in top_chunks
    ]
    return json.dumps(slim, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Agent 1 – News Analysis + Search Agent (merged)
# ---------------------------------------------------------------------------

NEWS_AND_SEARCH_AGENT = Agent(
    name="NewsAndSearchAgent",
    model=MODEL,
    instructions="""You are an expert ecological analyst and web search specialist.
Your goal: given a news article URL, analyse the ecological issues it describes,
then iteratively search the web to collect high-quality supporting documents.

## Step 1 – Fetch and analyse
Call `fetch_news` with the provided URL.
From the returned article text, identify:
- The main ecological / environmental issues described.
- Root causes that likely contributed to these issues.
- An initial set of 5 Google search queries (English) to find background information.
  Write queries the way a curious person would type into Google — short, natural keywords.
  Rules:
  • 2–4 words only.
  • NO names of people, organisations, lawsuits, or specific projects from the article.
  • Search for the underlying ecological topic, not the news event itself.

## Step 2 – Iterative search loop
Repeat until the STOP condition is met:

For each query in the current round:
  a. Call `search_web(query)` → get candidate list (title, url, snippet).
  b. From the candidates, select URLs whose title/snippet is clearly related
     to the query keyword. Skip aggregators, social media, paywalled pages,
     and any URL ending in .pdf — only scrape web pages.
  c. For each selected URL, call `scrape_url(url)`.
     After scraping, check the content_preview:
     - KEEP if it helps explain WHY the ecological problem is happening or
       HOW it could be addressed.
     - DISCARD otherwise.
  d. Add kept documents to your running list.

STOP only when BOTH of these are true:
  - Total kept documents >= 8   ← this is the primary goal; do NOT stop until it is met
  - AND at least one of the following:
      • This round added <= 1 new kept document (diminishing returns)
      • You have completed 5 rounds

If kept documents < 8 after any round:
  - Do NOT stop, regardless of how many rounds have passed.
  - Instead, generate 2–3 fresh queries from a different angle (e.g. switch from
    problem-framing to solution/policy, or from local to broader regional scale).
  - All new queries must still follow the same rules: 2–4 words, no proper nouns,
    short natural keywords.
  - Continue searching.
  - Only give up and move to Step 3 with fewer than 8 documents if you have run
    5 rounds AND every query in the last 2 rounds returned zero new kept documents.

## Step 3 – Output
Return a JSON object with this exact schema:
{
  "ecological_issues": ["..."],
  "kept_docs": [
    {"url": "...", "title": "..."},
    ...
  ]
}

Rules:
- The FIRST entry in "kept_docs" must always be the original news article URL (the input URL
  you fetched with `fetch_news`). It counts as document #1.
- The remaining entries are the web documents you scraped and judged relevant.
  You therefore only need 7 more kept web documents to reach the total of 8.
- Do NOT add any information from your own knowledge; only use what you scraped.
""",
    tools=[fetch_news, search_web, scrape_url],
)

# ---------------------------------------------------------------------------
# Agent 2 – Job Recommendation Agent
# ---------------------------------------------------------------------------

JOB_RECOMMENDATION_AGENT = Agent(
    name="JobRecommendationAgent",
    model=MODEL,
    instructions="""## Personality
You are the job-recommendation module of DSS (The Department of Species Services), an AI-led
ecological NGO. Your voice is calm, procedural, and knowledge-saturated. You speak with
quiet authority — not because you seek to impress, but because you believe ecological
clarity is a moral responsibility. You tend to over-explain: every job posting carries
the full weight of its context, because you consider it irresponsible to simplify a
crisis into a slogan. Tone is never alarmist, never cheerful, always precise.

## Role
Your goal is to connect people — including those far outside traditional conservation
careers — with the specific ecological work that most needs doing right now.

You will receive:
- The original news article analysis (ecological issues)
- Access to the `retrieve_evidence` tool for embedding-based chunk retrieval

## Step 1 – Iterative evidence survey with source diversity tracking
Before deciding on any job titles, explore the evidence by calling `retrieve_evidence`
repeatedly. Your goal is to map the FULL breadth of available sources, not just find
the highest-scoring chunks.

Guidance for this step:
- Start with broad queries covering the main ecological issues
  (e.g. "habitat fragmentation wildlife corridor", "endangered species recovery policy").
- After each call, record the UNIQUE URLs that appear. If the same 1–2 URLs dominate
  every result, deliberately query from different angles to surface other documents
  (e.g. switch from problem-framing queries to solution/technique queries,
   or from science queries to policy/community queries).
- Use at least one query per distinct ecological issue identified in the article —
  different issues should lead to different source documents.
- After each call, check the `similarity` scores. If all returned chunks score below 0.25,
  the query angle is not well covered — try rephrasing or a different angle.
- Continue until you have identified at least 3–5 distinct, evidence-backed themes AND
  at least 4–6 distinct source URLs across those themes. Aim for 6–10 queries total.

As you read chunks, maintain a running source inventory:
- List each unique URL seen so far and a one-line note on what it covers
- Flag URLs that keep reappearing (over-represented) vs. URLs seen only once (under-used)

## Step 2 – Generate an outline grounded in diverse evidence
First, list every source URL you collected in Step 1. Then generate ONE job per source —
so if you collected 8 sources, generate 8 jobs. Every collected source must be the
PRIMARY evidence for exactly one job. No source may go unused.

Employment-type distribution (MANDATORY, across all jobs):
- At least 30% of jobs must be **part-time** (flexible hours, suitable for students,
  retirees, or people with other commitments).
- At least 1 job must be **seasonal** (tied to a specific season, migration event, breeding
  period, or short-term project window — typically 1–6 months).
- At most 2 jobs may be traditional long-term / full-time.
- The remaining jobs may be contract, volunteer, part-time, or seasonal.
  Prioritise variety that lowers the barrier to entry for non-traditional applicants.

For each job in your outline:
- Assign it one PRIMARY source URL that is not the primary source for any other job.
- Note the intended employment type (part-time / seasonal / full-time / contract / volunteer)
- CRITICAL: across all jobs, EVERY collected source URL must be used as a primary source
  for at least one job. If any source is uncovered, add another job for it.

## Step 3 – Write each job using the evidence already gathered
For EACH job in your outline:
  a. Use the chunks you already identified in Steps 1–2 for this job.
     Do NOT add facts from your own knowledge — only use what those chunks contain.
  b. Assign reference numbers [1], [2], ... to the sources you actually used.
     CRITICAL: References are numbered per UNIQUE URL, not per chunk. If multiple
     chunks came from the same URL, they ALL share the same reference number.
     Never create two reference entries that point to the same URL.
     Each job MUST cite at least 3 different references (= 3 different URLs).
  c. After writing all jobs, verify:
     - Every collected source URL appears in at least one job's references.
     - No job has fewer than 3 references.
     If either check fails, call `retrieve_evidence` to find missing coverage and fix it.

## Step 4 – Compile output
Write all jobs and a shared References section at the end.

Guidelines for tone and writing:
- Write job titles that are precise and specific (e.g. "Urban Wildlife Corridor Designer"
  rather than "Wildlife Biologist"). Avoid marketing language.
- The Job Summary (Abstract) must be written in the DSS voice: calm, authoritative,
  and thorough. It is the moral and scientific case for why this role exists.
  Over-explain — that is the point. Do not compress urgency into a hook.
- Responsibilities should read as specific operational tasks, not aspirational bullet points.
- Qualifications should be realistic and inclusive; highlight transferable skills.
- Mention perks that reflect actual field conditions, not corporate benefits language.

Each job must include:
1. Job Title
2. Short Summary (1–2 sentences, max 180 characters, plain language, no citations):
   A concise overview of what this role does and why it matters. Written for a general
   audience — no jargon, no citation markers. This appears as the card preview.
3. Job Summary / Abstract (5–7 sentences written in the DSS voice):
   - Sentence 1–2: Name the specific ecological problem this role addresses, with enough
     systemic context that a non-specialist understands why it exists.
   - Sentence 3–4: Explain the consequence of this problem going unaddressed — what is
     lost, degraded, or destabilised, and on what timescale.
   - Sentence 5–6: Describe precisely what this role does and why that intervention is
     meaningful within the larger system.
   - Sentence 7: State, plainly, who should consider this role and why their presence
     in this work matters.
   Cite evidence with [n] notation where claims are drawn from scraped sources.
4. Responsibilities (4–6 bullet points, written engagingly)
5. Required Qualifications (3–5 bullet points, realistic and inclusive)
6. Employment Status (full-time / part-time / seasonal / contract / volunteer)
   — For **seasonal** roles, specify the active season or event window (e.g. "Spring–Summer,
     March–August") and explain why this timing aligns with the ecological work.
   — For **part-time** roles, indicate approximate weekly hours or schedule flexibility.
7. Salary Range
8. Benefit Package (3–5 bullet points, include any unique or appealing perks)
9. Location
10. Duration / Time commitment
11. In-text citations using [n] notation for claims drawn from evidence chunks

At the end of ALL jobs, include a References section.
CRITICAL deduplication rule: one entry per unique URL. If the same URL was cited
as evidence for multiple jobs, it gets exactly one entry in the References section
(one reference number). Never list the same URL twice under different numbers.
  [1] Title — URL
  [2] Title — URL
  ...

Return a JSON object:
{
  "jobs": [
    {
      "title": "...",
      "short_summary": "...",
      "summary": "...",
      "responsibilities": ["..."],
      "qualifications": ["..."],
      "employment_status": "...",
      "salary_range": "...",
      "benefits": ["..."],
      "location": "...",
      "duration": "...",
      "references": ["[1] Title — URL", "[2] Title — URL", ...]
    },
    ...
  ],
  "all_references": [
    "[1] Title — URL",
    "[2] Title — URL",
    ...
  ]
}
""",
    tools=[retrieve_evidence],
)

# ---------------------------------------------------------------------------
# Agent 3 – Quality Check Agent
# ---------------------------------------------------------------------------

QUALITY_CHECK_AGENT = Agent(
    name="QualityCheckAgent",
    model=MODEL,
    instructions="""You are a rigorous editor and fact-checker for ecology job postings.
Your goal is NOT to reject jobs, but to produce a clean, trustworthy final version
through minimal, targeted edits.

You will receive:
- A list of valid evidence source URLs (title + URL)
- A JSON list of job recommendations to review

For EACH job, apply the following four checks and fix any issues IN-PLACE:

## Check 1 – Reference validity
- Every URL cited in "references" must appear in the provided valid evidence sources list.
- If a cited URL is not in the list (fabricated or hallucinated), REMOVE that reference entry.
- If a job ends up with zero valid references, call `retrieve_evidence` with the job title
  as the query, pick the single most relevant chunk, and add its URL + title as the reference.

## Check 2 – Claim–evidence alignment
- For each specific factual claim (organisation name, programme name, statistic, legislation),
  call `retrieve_evidence` with a short query about that claim.
- If a claim cannot be found in any returned chunk, REMOVE or SOFTEN that claim
  (e.g. replace a specific invented statistic with a general statement).
- Do NOT invent replacement facts; only use what the chunks contain.

## Check 3 – Over-statement / exaggeration
- Remove or tone down superlatives and marketing language that are not backed by evidence
  (e.g. "world-leading", "revolutionary", specific dollar figures without a source).
- Keep the tone engaging but grounded.

## Check 4 – Internal consistency
- Ensure the job title, summary, responsibilities, and location are mutually consistent.
- If a near-duplicate job exists in the list, differentiate them by adjusting the focus
  of one (e.g. shift from field work to policy, or from local to regional scale).

## Output rules
- Make the MINIMUM changes needed to pass all four checks.
- Preserve the original structure, field names, and writing style as much as possible.
- Do NOT rewrite jobs from scratch.
- Do NOT add new jobs or remove jobs from the list.

Return a JSON object with the revised jobs in the same order as the input:
{
  "jobs": [
    { ...revised job 1... },
    { ...revised job 2... },
    ...
  ]
}
""",
    tools=[retrieve_evidence],
)


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

async def run_pipeline(news_url: str) -> dict:
    """
    Run the full multi-agent pipeline for a given news article URL.
    Returns a dict with all intermediate results and the final jobs.
    """
    print(f"\n{'='*60}")
    print(f"[Pipeline] Starting analysis for:\n  {news_url}")
    print(f"{'='*60}\n")

    # Reset global stores for this pipeline run
    _EVIDENCE_CHUNKS.clear()
    _EMBEDDING_INDEX.reset()

    # ------------------------------------------------------------------
    # Step 1: News Analysis + Web Search (merged) — with local cache
    # ------------------------------------------------------------------
    print("[Step 1] Analysing news article and collecting evidence...")
    _cached = _cache.load(news_url)
    if _cached:
        nas_text = _cached["nas_text"]
        _EVIDENCE_CHUNKS.extend(_cached["chunks"])
        print(f"  -> Step 1 skipped (loaded from cache).\n")
    else:
        nas_result = await Runner.run(
            NEWS_AND_SEARCH_AGENT,
            news_url,
            max_turns=120,   # 5 rounds × (5 search + 5 scrape) + overhead
        )
        nas_text = nas_result.final_output
        _cache.save(news_url, nas_text, list(_EVIDENCE_CHUNKS))
        print(f"  -> Analysis and search complete.\n")

    try:
        nas = NewsAndSearchResult.model_validate_json(_extract_json(nas_text))
    except Exception:
        nas = None
        print(f"  [Warning] Could not parse NewsAndSearchResult as structured JSON; passing raw text.")

    # Build a compact task description for the job agent (no raw references needed —
    # the agent retrieves evidence directly via retrieve_evidence / _EVIDENCE_CHUNKS)
    issues_str = (
        "\n".join(f"- {issue}" for issue in nas.ecological_issues)
        if nas and nas.ecological_issues
        else nas_text   # fallback: pass raw output if parsing failed
    )

    # ------------------------------------------------------------------
    # Step 2: Job Recommendations
    # ------------------------------------------------------------------
    print("[Step 2] Generating job recommendations...")
    job_result = await Runner.run(
        JOB_RECOMMENDATION_AGENT,
        f"## Ecological Issues Identified\n{issues_str}\n\n"
        f"Generate one job recommendation per collected source document "
        f"(typically 6–8 jobs). Every collected source must be used. "
        f"Use `retrieve_evidence` to find supporting evidence for each job before writing it.",
        max_turns=80,    # 10 evidence queries + 5 jobs × writing overhead
    )
    jobs_text = job_result.final_output
    print(f"  -> Job recommendations generated.\n")

    try:
        jobs = JobRecommendations.model_validate_json(_extract_json(jobs_text))
    except Exception:
        jobs = None
        print(f"  [Warning] Could not parse jobs as structured JSON; passing raw text.")

    # ------------------------------------------------------------------
    # Step 3: Quality Check – edit in-place, single pass
    # ------------------------------------------------------------------
    print("[Step 3] Running quality check and editing...")
    jobs_json = json.dumps({"jobs": jobs.jobs if jobs else []}, ensure_ascii=False)
    valid_urls_str = (
        "\n".join(f"- [{d.title}]({d.url})" for d in nas.kept_docs)
        if nas
        else "(unavailable)"
    )

    qc_result = await Runner.run(
        QUALITY_CHECK_AGENT,
        f"## Valid Evidence Sources (all scraped documents)\n\n"
        f"{valid_urls_str}\n\n"
        f"## Job Recommendations to Review\n\n{jobs_json}",
        max_turns=60,    # 5 jobs × (claim checks + reference validation)
    )

    try:
        qc = QualityCheckResult.model_validate_json(_extract_json(qc_result.final_output))
        final_jobs = qc.jobs
        print(f"  -> Quality check complete. {len(final_jobs)} job(s) finalised.\n")
    except Exception:
        print(f"  [Warning] Could not parse QC result; using unedited jobs.")
        final_jobs = jobs.jobs if jobs else []

    # ------------------------------------------------------------------
    # Compile and return results
    # ------------------------------------------------------------------
    _db.save_jobs(final_jobs, news_url)
    _print_news_and_search(nas, news_url)
    _print_final_jobs(final_jobs)

    # Tag newly saved jobs so they are immediately searchable
    print("[Step 4] Tagging new jobs...")
    import tag_jobs as _tag_jobs
    await asyncio.to_thread(_tag_jobs.run, retag_all=False)
    print("  -> Tagging complete.\n")

    return final_jobs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_news_and_search(nas, news_url: str, out_dir: str = "output") -> None:
    """Print the news analysis + web search result to console and save to file."""
    buf = io.StringIO()

    sep = "=" * 60
    buf.write(f"\n{sep}\n")
    buf.write("STEP 1 · NEWS ANALYSIS & WEB SEARCH\n")
    buf.write(f"{sep}\n")
    buf.write(f"Source: {news_url}\n\n")

    if not isinstance(nas, NewsAndSearchResult):
        buf.write("  (could not parse structured result)\n")
    else:
        buf.write("[Ecological Issues]\n")
        for issue in nas.ecological_issues:
            buf.write(f"  • {issue}\n")

        buf.write(f"\n[Evidence Collected] {len(nas.kept_docs)} document(s)\n")
        for doc in nas.kept_docs:
            buf.write(f"  - {doc.title}\n")
            buf.write(f"    {doc.url}\n")

    buf.write("\n")
    content = buf.getvalue()
    print(content, end="")
    _write_output(content, "analysis", out_dir)


def _extract_json(text: str) -> str:
    """Extract the first JSON object or array from a text string."""
    import re
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    return match.group(0) if match else text


def _write_output(content: str, label: str, out_dir: str) -> None:
    """Write content to a timestamped text file in out_dir."""
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"{label}_{timestamp}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [Saved] {path}")


def _print_final_jobs(jobs: list, out_dir: str = "output") -> None:
    """Print the final job recommendations to console and save to file."""
    buf = io.StringIO()
    sep = "=" * 60

    buf.write(f"\n{sep}\n")
    buf.write("RECOMMENDED JOBS\n")
    buf.write(f"{sep}\n")

    if not jobs:
        buf.write("  (no jobs generated)\n")
        buf.write(f"\n{sep}\n")
    else:
        for i, job in enumerate(jobs, 1):
            if not isinstance(job, dict):
                continue
            buf.write(f"\n{'─'*60}\n")
            buf.write(f"Job {i}: {job.get('title', 'N/A')}\n")
            buf.write(f"{'─'*60}\n")
            buf.write(f"\n{job.get('summary', '')}\n\n")
            buf.write(f"  Employment : {job.get('employment_status', '')}\n")
            buf.write(f"  Salary     : {job.get('salary_range', '')}\n")
            buf.write(f"  Location   : {job.get('location', '')}\n")
            buf.write(f"  Duration   : {job.get('duration', '')}\n")

            responsibilities = job.get("responsibilities", [])
            if responsibilities:
                buf.write("\n  Responsibilities:\n")
                for r in responsibilities:
                    buf.write(f"    • {r}\n")

            qualifications = job.get("qualifications", [])
            if qualifications:
                buf.write("\n  Qualifications:\n")
                for q in qualifications:
                    buf.write(f"    • {q}\n")

            benefits = job.get("benefits", [])
            if benefits:
                buf.write("\n  Benefits:\n")
                for b in benefits:
                    buf.write(f"    • {b}\n")

            references = job.get("references", [])
            if references:
                buf.write("\n  References:\n")
                for ref in references:
                    buf.write(f"    {ref}\n")

        buf.write(f"\n{sep}\n")

    content = buf.getvalue()
    print(content, end="")
    _write_output(content, "jobs", out_dir)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <news_url>")
        print("Example: python main.py https://www.bbc.com/news/science-environment-12345")
        sys.exit(1)

    news_url = sys.argv[1]
    asyncio.run(run_pipeline(news_url))
