# DSS — The Department of Species Services

An AI-led ecological job recommendation platform. A multi-agent pipeline analyses ecology news articles, collects supporting evidence from the web, and generates grounded job recommendations. Users answer 5 questions; their answers are matched against job tags to return 8 personalised results. Each job card displays a QR code linking to a full detail page hosted on Netlify.

---

## How It Works

```
News URL
   │
   ▼
┌─────────────────────────┐
│   NewsAndSearchAgent    │  Fetches the article, identifies ecological issues,
│                         │  iteratively searches the web until ≥ 8 supporting
│  fetch_news             │  documents are collected.
│  search_web             │  Output: ecological_issues + kept_docs
│  scrape_url             │  Side-effect: populates _EVIDENCE_CHUNKS
└────────────┬────────────┘
             │  ← result cached to cache/step1/<url_hash>.json
             ▼
┌─────────────────────────┐
│ JobRecommendationAgent  │  Generates one job per collected source (typically
│                         │  6–8 jobs). Voice: calm, procedural, knowledge-saturated.
│  retrieve_evidence      │  Each job's Abstract explains the ecological problem
│                         │  in full — significance, consequence, and intervention.
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│   QualityCheckAgent     │  Edits each job in-place (minimum changes):
│                         │  removes fabricated references, softens unsupported
│  retrieve_evidence      │  claims, fixes inconsistencies.
└────────────┬────────────┘
             │
             ▼
        jobs.db (SQLite)
             │
             ▼
     FastAPI server (:8000)
             │
             ▼
      React frontend (:5173)
```

---

## Project Structure

```
DSS Project/
├── main.py          # Agent definitions, tools, pipeline orchestration
├── search.py        # Web search (SerpAPI), scraping, chunking, FAISS retrieval
├── server.py        # FastAPI server — exposes /api/jobs to the frontend
├── db.py            # SQLite job database (jobs.db)
├── cache.py         # Step 1 result cache (cache/step1/)
├── tag_jobs.py      # Tag all jobs in jobs.db using the 5-question taxonomy
├── export_static.py # Export all jobs as static HTML files for Netlify
├── requirements.txt
│
├── cache/           # Auto-created on first run
│   └── step1/
│       └── <url_hash>.json   # Cached Step 1 output per news URL
│
├── jobs.db          # SQLite database — 288 tagged jobs included
├── output/          # Auto-created — plain-text logs of each pipeline run
│
└── frontend/        # React + Vite
    ├── src/
    │   ├── App.jsx              # Screen state machine
    │   ├── api.js               # Backend API interface
    │   └── components/
    │       ├── SplashScreen.jsx
    │       ├── OpeningScreen.jsx
    │       ├── QuestionScreen.jsx
    │       ├── LoadingScreen.jsx
    │       └── ResultsScreen.jsx
    └── package.json
```

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- API access: [OhMyGPT](https://ohmygpt.com) (or any OpenAI-compatible proxy)
- SerpAPI key for Google Search

---

## Backend Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install Playwright browser (for JS-rendered pages)
playwright install chromium
```

### Environment Variables

The following variables are optional — defaults are hardcoded for development.
For production, set them in your environment or a `.env` file.

| Variable | Default | Description |
|---|---|---|
| `OHMYGPT_API_KEY` | (hardcoded in main.py) | API key for chat completions + embeddings |
| `OHMYGPT_BASE_URL` | `https://api.ohmygpt.com/v1` | API base URL |
| `OHMYGPT_MODEL` | `gpt-5.1` | Model used by all agents |

The SerpAPI key is currently set directly in `search.py` (`SERPAPI_API_KEY`). Move it to an environment variable before deploying.

---

## Running the Pipeline

```bash
python main.py <news_article_url>
```

**Example:**

```bash
python main.py "https://calmatters.org/environment/2026/01/san-diego-sues-razor-wire-fencing/"
```

**What happens:**

1. **Step 1** — Fetches and analyses the article, searches the web for supporting documents. Result is saved to `cache/step1/<hash>.json`.
2. **Step 2** — Generates one job per collected source (typically 6–8 jobs), each grounded in evidence.
3. **Step 3** — Quality-checks each job: removes hallucinated references, softens unsupported claims.
4. Jobs are saved to `jobs.db`, automatically tagged, and a plain-text log is written to `output/`.

**Repeat runs on the same URL skip Step 1** — chunks are loaded from cache and Steps 2–3 run fresh. This saves significant time and API cost.

### Tagging jobs manually

If you need to tag jobs that were saved without tags (e.g. from an older run):

```bash
python tag_jobs.py           # tags only untagged jobs
python tag_jobs.py --all     # re-tags every job
```

---

## Running the API Server

```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` makes the server reachable from other devices on the same network
(required for QR code scanning from phones/tablets).

The server exposes:

| Endpoint | Method | Description |
|---|---|---|
| `/api/jobs` | POST | Accepts user questionnaire answers, returns 8 matched jobs (random sample from best-scoring tier) |
| `/api/jobs/{id}` | GET | Returns a single job as JSON |
| `/jobs/{id}` | GET | Human-readable HTML job detail page (QR code target, local fallback) |
| `/api/health` | GET | Health check |

---

## Running the Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite will print two URLs:

```
  ➜  Local:   http://localhost:5173/
  ➜  Network: http://<your-ip>:5173/
```

**For QR code scanning to work**, open the **Network** URL (the `<your-ip>` one) on the display device. When the page is loaded via a real IP address, every job card's QR code automatically encodes `http://<your-ip>:8000/jobs/{id}` — a URL phones on the same network can reach.

The frontend walks users through a 5-question questionnaire, then displays job cards. Each card shows a placeholder image, a short summary, and a QR code. Scanning the QR code opens the full job detail page in the phone's browser.

**To point QR codes at the Netlify static site** (recommended — works from any network, not just LAN), create `frontend/.env.local`:

```
VITE_QR_BASE=https://gleaming-marzipan-b1cb74.netlify.app
```

**To point the frontend at a different API URL**, add to `frontend/.env.local`:

```
VITE_API_URL=http://<your-ip>:8000
```

### Deploying job pages to Netlify

```bash
python export_static.py           # generates output/static/jobs/<id>.html
netlify deploy --dir output/static --prod --site <your-site-id>
```

---

## Full Local Setup (all three together)

```bash
# Terminal 1 — run the pipeline to populate the database
source .venv/bin/activate
python main.py "<your_news_url>"

# Terminal 2 — start the API server (--host 0.0.0.0 lets phones on LAN scan QR codes)
source .venv/bin/activate
uvicorn server:app --reload --host 0.0.0.0 --port 8000

# Terminal 3 — start the frontend (--host is built into npm run dev)
cd frontend
npm run dev
# Then open the Network URL printed by Vite (e.g. http://192.168.x.x:5173)
# so that QR codes encode the correct IP address for phone scanning
```
