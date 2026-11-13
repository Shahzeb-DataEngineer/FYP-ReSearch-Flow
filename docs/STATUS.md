# ReSearch Flow revival status

Last updated: 2026-11-12. Base branch: `Shahzeb-Ali-Web-Developer`.
Repo: https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow

## What is done

The project was revived from its final-year state (last commit 2026-05-08)
into a working, zero-cost, self-hosted system. All pull requests below were
merged with regular merges and verified live before merging. All commits and
PRs are authored as Shahzeb Ali.

| PR | Title | Branch | Commits |
|----|-------|--------|---------|
| [#3](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/3) | feat: replace paid llm apis with local ollama and add free paper sources | ollama-migration | 55f7ae24, ba38ae1d, 959c6b95 |
| [#4](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/4) | feat: add pubmed, doaj and unpaywall paper sources | add-free-sources | 5ac04c52 |
| [#5](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/5) | fix: resolve audit blockers, add docker and tests | fix-audit-blockers | 01d26ed7, 18d667f |
| [#6](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/6) | fix: lock down cors, fix papers api, add schema and lint fixes | fix-remaining-blockers | 89913e7a, da257b2f |
| [#7](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/7) | docs: update readme and add measured evaluation | docs-eval-packaging | 11efa2c0 |
| [#8](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/8) | fix: fetch europe pmc full text xml when pdf download is blocked | fix-europe-pmc-pdf | 2e6f09a0 |
| [#9](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/9) | fix: make summary json robust with repair retry and chunk splitting | fix-summary-json | 36b0fb6b |

What changed, in short:

- Paid LLM stack removed (OpenAI, OpenRouter, Pinecone, SerpAPI/Google
  Scholar). Local Ollama instead: qwen2.5:3b chat, nomic-embed-text
  embeddings, FAISS + BM25 retrieval. No paid API keys, no per-query cost.
- 10 paper sources: OpenAlex, arXiv, CORE, PMC, Semantic Scholar,
  Crossref, Europe PMC, PubMed, DOAJ, Unpaywall (DOI lookup).
- Europe PMC full text fetched as JATS XML (the website blocks direct PDF
  downloads behind a bot-protection challenge).
- Full-text summarization fixed for long papers: chunk splitting past the
  8192-token context, paragraph structure in JATS text, JSON repair retry.
- Draft generation rewritten for Ollama; figure analysis off by default
  (no local vision model configured).
- Security and hygiene: committed `frontend/.env` removed from git tracking,
  CORS locked down from `*` to local origins, API-key check on the
  destructive chat-history route, `research_papers` table schema added,
  Papers API doubled path fixed.
- Frontend: Google Scholar removed, Crossref/Europe PMC/PubMed/DOAJ/
  Unpaywall clients added, missing `supabase` import fixed, conditional
  hooks fixed in Results.jsx DetailPanel and FloatingBubbles.jsx.
- Docker + Docker Compose for a one-command demo, CI on pull requests,
  44 backend unit tests, README updated, measured evaluation in
  `docs/evaluation.md`, recommender brief in `docs/recommender-brief.md`.

## Measured numbers (live, 2026-11-12, CPU-only machine, qwen2.5:3b)

- Evaluation (10 questions, 5 real papers): 9 correct, 1 partially correct,
  0 wrong. All 10 calls HTTP 200. Total LLM time about 38 minutes.
- Full-text summary of a 54,556-char Europe PMC paper: HTTP 200 in
  1107.4 s, all four fields populated with accurate content, zero placeholders.
- Search: 1.0-2.8 s per source. Abstract-based summary: 66-109 s.
  Full-PDF summary: 10-18 minutes per paper on CPU.
- Backend unit tests: 45/45 pass. Frontend lint: 7 problems (0 errors,
  7 warnings), down from 85 at the start of the revival.
- The old README performance numbers (1.8 s first results, 6-9 s full
  results, 38% dedup, RAG 74%/18%/8%) were removed: they were never measured.

## Still open

- **UNPAYWALL_EMAIL**: set locally (2026-11-13) to the user's Gmail in
  `backend/.env` (gitignored, never committed) and verified live: a DOI
  lookup now returns real open-access data instead of HTTP 422. Note:
  the service previously read `os.getenv` directly, which missed
  `backend/.env`; it now reads the value through Settings, so the
  `backend/.env` file works. Deployments still need the variable set in
  their own environment. The placeholder default remains unusable.
- **Supabase key rotation**: a Supabase anon key committed to git history in
  the original project is still visible in 8 history commits. Rotate it in
  the Supabase dashboard. The file itself was removed from git tracking.
- **Git history rewrite**: purging `frontend/.env` from history is
  destructive and has not been done; it needs an explicit decision.
- **Proper JWT auth**: backend authentication still needs a full
  Supabase-JWT design (frontend + backend change, needs a live Supabase
  project to test against).
- **Docker build/run**: the Dockerfile and Compose files have not been built
  or run (no Docker on the machine used for this work).
- **MS application details**: target countries/programs and application
  deadlines have not been decided yet. These decide whether the demo or a
  written paper comes first.
