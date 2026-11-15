# ReSearch Flow  
### AI-Powered Academic Research Assistant  

ReSearch Flow is a full-stack AI-driven platform designed to simplify and accelerate the academic literature review process. It integrates multi-source research retrieval, intelligent deduplication, AI summarization, conversational Q&A, citation network visualization, and draft generation into a single unified system.

---

## Try it in 2 minutes

No account needed to search. Log in (free, via Supabase) only when you
want the AI features.

1. **Search** - type a topic in the search bar. Papers come back from
   ten free sources (OpenAlex, arXiv, Crossref, Europe PMC, PubMed,
   DOAJ, Semantic Scholar, CORE, PMC, Unpaywall) with duplicates
   removed.
2. **Summarize** - open a paper and hit Summarize. You get a structured
   summary (problem, method, results, conclusion) from the full text
   when it is available. Runs on a local model, no paid API key.
3. **Ask** - ask a question about the paper in plain language. Answers
   come from the paper itself (RAG), not from general knowledge.
4. **Draft** - generate a structured draft from a paper, then edit it
   in the editor. Save papers, notes, and searches to your workspace.

Everything AI runs locally on Ollama, so there is no per-token bill.
Full-paper summaries take 2-5 minutes on a CPU-only machine; abstract
summaries take about 1-2 minutes.

To self-host it, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## Interface

The interface was fully redesigned in November 2026, taking cues from
Perplexity, Elicit, NotebookLM, Linear and Raycast. The direction is
"warm paper by day, focused dark by night, keyboard-first":

- **App shell** - a slim 240px sidebar (Search, PRISMA Review, Citation
  Graph, My Library, Saved Searches, Pricing) with a live local-model
  and $0.00 cost footer, plus a slim glassy top bar. On mobile the
  sidebar becomes a slide-over drawer.
- **Dark mode** - a real dark theme built on semantic color tokens, not
  an inverted filter. The toggle persists in localStorage and defaults
  to the OS preference. Teal is the single accent in both themes
  (`#0F766E` light, `#2DD4BF` dark).
- **Command palette** - press Ctrl/Cmd+K anywhere for grouped actions,
  recent searches and live search suggestions, with full keyboard
  navigation.
- **Question-first home** - a centered search hero with a serif
  headline (Fraunces) and honest stats underneath. No unmeasured
  marketing numbers: the home page shows only numbers the project can
  stand behind (10 free sources, 8 AI workflows, $0.00 total cost,
  156 tests passing).
- **Paper cards** - soft white rounded cards with a source pill,
  year/venue/authors meta, citation count and a teal selection ring.
  Skeleton loaders replace spinners while results load.
- **Logo** - a new mark in `frontend/public/logo.svg`: three nodes
  joined by one flowing curve inside a teal rounded square, the flow
  from question to evidence to draft. It also serves as the favicon.

The full design brief, palette, type scale and per-page changes are in
[docs/UI_REVAMP.md](docs/UI_REVAMP.md).

What each main view looks like: the home page is a question box with
honest stats and a feature grid; search results are scannable paper
cards with a filter panel and a detail slide-over; the chat view shows
answers with source chips; Deep Review and PRISMA are form cards with
progress states and evidence-first result cards; My Library shows
library stats, Zotero import and the knowledge graph; the model picker
and usage panel show the active local model and the $0.00 cost readout.

---

## Problem Statement

Modern research workflows are fragmented across multiple platforms such as Google Scholar, PubMed, and arXiv. Researchers face challenges including:

- Switching between multiple databases  
- Duplicate results across sources  
- Time-consuming paper analysis  
- Lack of visualization for citation relationships  
- No unified AI-assisted research workflow  

---

## Solution

ReSearch Flow provides an **end-to-end research assistant** that:

- Aggregates papers from multiple academic sources  
- Removes duplicates intelligently  
- Generates AI-powered summaries  
- Enables conversational Q&A on papers (RAG)  
- Visualizes citation relationships  
- Assists in research draft writing  

---

## Key Features

### Multi-Source Search
- OpenAlex, arXiv, CORE, PMC, Semantic Scholar, Crossref, Europe PMC, PubMed, DOAJ, Unpaywall (DOI lookup for open-access PDF links)  
- Per-source search with progressive loading; service-level dedup by identifiers (PMCID, DOI, title)  

### AI Summarization
- Local Ollama model (qwen2.5:7b on a 16 GB laptop, qwen2.5:3b on low-RAM machines)  
- Structured summaries, no paid API key  
- Extracts insights from full PDF content  

### RAG-based Chat
- Ask questions about any paper  
- Hybrid retrieval (Pinecone + BM25, nomic-embed-text)  
- Context-aware responses  

### Citation Mesh
- Interactive graph visualization (Cytoscape.js)  
- Metrics: PageRank, Influence Score, Citation Velocity  

### Draft Generation
- AI-generated structured drafts  
- Text-based only by default; figure analysis is off unless a local vision model is configured (`OLLAMA_VISION_MODEL`, e.g. `llava:7b`)  

### User Workspace
- Save articles  
- Manage search history  
- Add personal notes  
- Private knowledge graph over saved papers and notes, with free
  Zotero sync and locally computed new-paper alerts  

### Deep Review and verifiable citations
- Deep Review: a multi-step synthesis that runs sub-queries across
  sources, extracts per-paper evidence and returns a cited answer
- Sentence-level citation verification (embedding similarity) and
  retraction, open-access, peer-reviewed and preprint badges per paper  

### Systematic review (PRISMA)
- Free PRISMA flow: screening with include/exclude reasons, dual-pass
  adjudication, auto PRISMA diagram data and a screening-accuracy
  report (AI screening is a first pass, human verification is required)  

### Citation graph and gap finder
- Citation and similarity maps from free OpenAlex and Semantic Scholar
  data, under-cited clusters and unanswered-question detection  

### Transparent model picker and cost meter
- Pick the local Ollama model from the UI; the usage panel shows the
  cost of every run and the cloud price avoided. Total spent is always
  $0.00  

### Honest drafting
- Drafts with per-sentence support flags and a pre-export retraction
  check that blocks export when a cited paper is retracted  

### Performance Optimization
- Background caching (Supabase)  
- Redis-based chat session storage  

---

## System Architecture
Frontend (React + Vite)
>
Backend (FastAPI)
>
AI Layer (LangChain + local Ollama)
>
Databases (Supabase, Pinecone, Redis)
>
External APIs (OpenAlex, arXiv, etc.)


---

## Tech Stack

### Frontend
- React 19 + Vite  
- Tailwind CSS  
- Framer Motion  
- Cytoscape.js  

### Backend
- FastAPI (Python 3.11)  
- PyMuPDF (PDF parsing)  
- Pandas  

### AI & ML
- Ollama (local, zero cost): qwen2.5:7b / qwen2.5:3b chat, nomic-embed-text embeddings  
- LangChain  
- Pinecone (serverless vector store, Starter free tier)  
- BM25 Retriever  

### Database & Storage
- Supabase (PostgreSQL + Auth)  
- Upstash Redis  
- Neo4j (optional)  

---

## Zero-cost note

This project uses no paid APIs. LLM work runs on a local Ollama model,
search uses free sources (OpenAlex, arXiv, CORE, PMC, Semantic Scholar,
Crossref, Europe PMC, PubMed, DOAJ, Unpaywall), and vector search uses
Pinecone on the Starter free tier ($0, no credit card; embeddings stay
local). The cross-paper library ask still uses a local FAISS index over
saved abstracts and notes. Google Scholar was removed because it needed the paid
SerpAPI service.

To run the AI features:

```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

On a low-RAM machine, use `qwen2.5:3b` instead and set
`OLLAMA_CHAT_MODEL=qwen2.5:3b` in your `.env`. See `.env.example`.

---

## Run with Docker (one command)

Copy `.env.example` to `.env` and fill in real values first (at
minimum `PINECONE_API_KEY` for RAG chat and `UNPAYWALL_EMAIL`);
Compose reads `.env` and passes every setting to the containers.

```bash
docker compose up --build
```

This starts the backend on http://localhost:8000 and the frontend on
http://localhost:3000 (nginx serves the built Vite app and proxies
`/api/` to the backend).

Ollama is **not** bundled in Compose: it is an external service and
must already be running on the host before you start the stack
(`ollama serve`, then `ollama pull qwen2.5:3b` and
`ollama pull nomic-embed-text`). The backend reaches it through
`OLLAMA_BASE_URL`, which defaults in Compose to
`http://host.docker.internal:11434` (a standard Ollama install). If
your Ollama listens on another port, for example a manual serve on
11435, set it before starting Compose:

```bash
OLLAMA_BASE_URL=http://host.docker.internal:11435 docker compose up --build
```

Set `UNPAYWALL_EMAIL` to a real project address if you want Unpaywall
lookups to work (the placeholder is rejected by Unpaywall with
HTTP 422). See `.env.example` for the other optional settings.

---

## Tests

Backend tests are plain stdlib `unittest` (no pytest dependency).
From `backend/`:

```bash
python -m unittest discover -s src/app/tests -v
```

156 tests, covering dedup helpers, paper-source parsing, the new
workflows (Deep Review, citations, PRISMA, citation graph, knowledge
graph, model picker, cost meter, honest drafting) and the production
hardening (JWT auth, rate limiting, readiness) with fixtures and
mocks: no network calls, no Ollama, no live APIs.

---

## Database Design

The system uses a hybrid approach:

- **Structured Data** → Supabase (users, saved searches, history)  
- **Cached Papers** → research_papers table  
- **Vector Embeddings** → Pinecone (serverless index, paper_id filter)  
- **Session Data** → Redis  

---

## Workflow Overview

1. User enters search query  
2. System queries multiple APIs in parallel  
3. Results are deduplicated  
4. Cached in database  
5. AI modules process data (summary, chat, draft)  
6. Results are displayed with interactive visualizations  

---

## Results & Performance

No performance numbers are claimed here: the figures in earlier
versions of this README (first results ~1.8s, full results 6-9s,
~38% dedup reduction, RAG 74% / 18% / 8%) were never measured
against this codebase and have been removed. The only measured
results are in `docs/evaluation.md`, a fixed 10-question run on
2026-11-12 with the local Ollama model.

Measured latency on a CPU-only machine (no GPU, qwen2.5:3b) is
honest but slow: a structured summary took ~95s, a RAG answer
~36s, and a full draft 4-10 minutes. Search itself is fast
(under ~3s per source). A laptop with a GPU, or the 7B model
(`qwen2.5:7b`), will be much faster.  

---

## Authentication

- Supabase Auth (JWT-based)  
- Google OAuth support  
- The `/saved-searches` page redirects to login when there is no
  session; search and results are intentionally public. Chat
  ask/history and draft generation verify the Supabase JWT on the
  backend (HS256 with `SUPABASE_JWT_SECRET`, Auth API fallback),
  chat sessions are scoped per user, and per-IP rate limiting
  applies (summarize/ask 10/min, chat 20/min, draft 2/hour).  

---

## Testing

- Backend unit tests: 156 stdlib `unittest` tests covering dedup
  helpers, paper-source parsing, the AI workflows and the production
  hardening, with fixtures and mocks only (no network, no Ollama).
  Run them from `backend/` with
  `python -m unittest discover -s src/app/tests -v`.
- A fixed 10-question live evaluation against the real backend and
  local Ollama is recorded in `docs/evaluation.md`.
- No integration or end-to-end test suite exists yet.  

---

## Limitations

- Requires open-access PDFs for full AI analysis  
- API rate limits on free sources  
- Initial RAG indexing delay for new papers  

---

## Future Work

- Larger evaluation set and a GPU run for latency comparison  
- Multi-modal RAG (text + figures, once a vision model is configured)  
- Chrome extension  
- Collaborative research workspace  
- Mobile app  
- OCR for scanned PDFs  

---

## Team

- **Haroon Mahmood (BSDSF22M020@pucit.edu.pk)**  
- **Maryam Abid (BSDSF22M028pucit.edu.pk)**  
- **Areesha Rizwan (BSDSF22M048pucit.edu.pk)**  
- **Shahzeb Ali (BSDSF22M054pucit.edu.pk)**  

---

## Supervisor

**Dr. Khurram Shahzad**  
Faculty of Computing & Information Technology  
University of the Punjab, Lahore  

---

## License

This project is developed for academic purposes as a Final Year Project.  

The system follows a modular layered architecture:
