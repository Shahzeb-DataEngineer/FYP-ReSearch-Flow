# Recommender brief: ReSearch Flow (Shahzeb Ali)

Prepared for Dr. Khurram Shahzad, supervisor of the final year project
"ReSearch Flow", PUCIT BS Data Science. This brief gives the facts about the
project and Shahzeb Ali's part in it, for use in a recommendation letter for
his MS scholarship application abroad. It contains only facts from the project
itself; it does not state grades, rankings, or claims that were not measured.

## What ReSearch Flow is

ReSearch Flow is an AI-powered academic research assistant. A user searches
for research papers across several free sources, reads an AI summary of a
paper, asks questions about it in a RAG chat, generates a draft section from
it, and explores a citation network (Citation Mesh) built from the papers.
The stack is a React 19 + Vite frontend and a FastAPI Python backend, with
Supabase (PostgreSQL + Auth) for saved articles and notes.

## What Shahzeb Ali built

Shahzeb was the backend developer of the four-person final year team
(frontend: Maryam Abid; deployment: Haroon Mahmood; database: Areesha Rizwan).
After the degree ended, he revived and rebuilt the project on his own
(November 2026) to make it a working, zero-cost, self-hosted system:

- Replaced the paid LLM stack (OpenAI, OpenRouter, Pinecone, SerpAPI/Google
  Scholar) with a fully local setup: Ollama (qwen2.5:3b chat model,
  nomic-embed-text embeddings) and FAISS + BM25 retrieval. The project now
  runs with no paid API keys and no per-query cost.
- Added free paper sources so the system now searches 10 sources:
  OpenAlex, arXiv, CORE, PMC, Semantic Scholar, Crossref, Europe PMC,
  PubMed, DOAJ, and Unpaywall (DOI lookup for open-access PDFs).
- Fixed the Europe PMC PDF extraction failure: europepmc.org blocks direct
  PDF downloads behind a bot-protection challenge, so the backend now fetches
  the same full text as JATS XML from the Europe PMC REST API.
- Fixed full-text summarization failing on long papers (chunk splitting past
  the model's 8192-token context window, paragraph structure in JATS text,
  and a JSON repair retry so the model output parses reliably).
- Fixed the remaining audit blockers found in a full code review: removed a
  committed `.env` file from git tracking, locked CORS down from `*` to
  local origins, fixed the Papers API route, added the `research_papers`
  table schema, fixed frontend hook and import errors, added Docker and
  Docker Compose for a one-command demo, and added CI on pull requests.
- All of this work landed as reviewed pull requests #3 to #9 on the
  project's GitHub repository (Shahzeb-DataEngineer/FYP-ReSearch-Flow),
  each with live tests before merging.

## Measured results (not estimates)

The only measured evaluation is in `docs/evaluation.md` (2026-11-12), run
live against the local backend with the 3B model on a CPU-only machine
(4 CPUs, 7.7 GB RAM, no GPU):

- 10-question evaluation (5 summaries, 5 RAG questions, 5 real papers):
  9 correct, 1 partially correct, 0 wrong. All 10 calls returned HTTP 200.
- Full-text summarization of a 54,556-character Europe PMC paper returned
  all four fields populated with accurate content, in 1107.4 s.
- Backend unit tests: 44/44 pass. Frontend lint: 10 problems (3 errors,
  7 warnings), down from 85 at the start of the revival.
- Search is fast: 1.0-2.8 s per source. Latency is the honest limitation:
  full-PDF summarization takes 10-18 minutes per paper on this CPU-only
  machine; abstract-based calls take 66-109 s.

## What the project demonstrates

- Data engineering: multi-source ingestion and deduplication across 10
  paper APIs, a PostgreSQL schema for cached papers, and a reproducible
  evaluation with measured numbers.
- LLM systems: local model deployment (Ollama), retrieval-augmented
  generation with FAISS + BM25, structured-output parsing with repair
  retries, and working within a small model's context limits.
- Cost-conscious engineering: the whole system is self-hosted and free to
  run, which was a deliberate design constraint, not an accident.

## Open items (stated honestly)

- Unpaywall lookups need a real project email address configured; the
  placeholder is rejected by the Unpaywall API.
- A Supabase key that was committed to git history in the original project
  still needs rotating in the Supabase dashboard.
- Backend authentication still needs a full Supabase-JWT design; the current
  setup relies on the frontend's Supabase session.
- The Docker files have not yet been built or run (no Docker on the machine
  used for this work).
