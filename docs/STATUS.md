# ReSearch Flow revival status

Last updated: 2026-11-14. Base branch: `Shahzeb-Ali-Web-Developer`.
Repo: https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow

## What is done

The project was revived from its final-year state (last commit 2026-05-08)
into a working, zero-cost, self-hosted system, and then built up to a
live-shippable product. All pull requests below were merged with regular
merges and verified live before merging. All commits and PRs are authored
as Shahzeb Ali.

| PR | Title | Branch | Merge commit |
|----|-------|--------|--------------|
| [#3](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/3) | feat: replace paid llm apis with local ollama and add free paper sources | ollama-migration | - |
| [#4](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/4) | feat: add pubmed, doaj and unpaywall paper sources | add-free-sources | - |
| [#5](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/5) | fix: resolve audit blockers, add docker and tests | fix-audit-blockers | - |
| [#6](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/6) | fix: lock down cors, fix papers api, add schema and lint fixes | fix-remaining-blockers | - |
| [#7](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/7) | docs: update readme and add measured evaluation | docs-eval-packaging | - |
| [#8](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/8) | fix: fetch europe pmc full text xml when pdf download is blocked | fix-europe-pmc-pdf | - |
| [#9](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/9) | fix: make summary json robust with repair retry and chunk splitting | fix-summary-json | - |
| [#10](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/10) | docs: add recommender brief, evaluation follow-up and status | scholarship-packaging | a4868cc |
| [#11](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/11) | fix: wire unpaywall email through settings and polish frontend | world-class-polish | 9f35489 |
| [#12](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/12) | feat: production-ready auth, rate limiting and deployment guide | production-ready | 5010611 |
| [#13](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/13) | competitor moves 1-2: deep review, verifiable citations, openalex api key | competitor-moves-1-2 | 3c450ec |
| [#14](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/14) | competitor moves 3-4: oa full-text bridge, free prisma systematic review | competitor-moves-3-4 | ad65c53 |
| [#15](https://github.com/Shahzeb-DataEngineer/FYP-ReSearch-Flow/pull/15) | competitor moves 5-6: citation graph gap finder, private knowledge graph | competitor-moves-5-6 | c0c63d6 |

Moves 7-8 are implemented and verified locally on branch
`competitor-moves-7-8` (from base head `c0c63d6`, 19 changed files);
the PR is pending the user's tap on the GitHub approval card, then it
can be opened and merged. See `docs/COMPETITOR_MOVES_7_8.md`.

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
  156 backend unit tests, README updated, measured evaluation in
  `docs/evaluation.md`, recommender brief in `docs/recommender-brief.md`.

### Production-ready (PR #12, merged 2026-11-13)

- Supabase JWT verification on chat ask/history and draft generate
  (HS256 with `SUPABASE_JWT_SECRET`, Auth API fallback, 503 when
  Supabase unset). Chat sessions scoped per user.
- Public search stays usable without login.
- Per-IP rate limiting (summarize/ask 10/min, chat 20/min, draft
  2/hour, 429 with Retry-After), `GET /ready` (200 ready / 503
  degraded), sanitized 500s, frontend AI-down banner.
- Live verified on the merged base: `/health` 200, `/ready` 200,
  summarize 68.7s, RAG ask 16.6s with signed test JWT (401 without
  token, 401 bad token), draft 12m58s.

### Competitor moves (all 8 done; 1-6 merged, 7-8 verified locally)

- Move 1 - Deep Review (`POST /api/v1/review/deep`): LLM sub-queries,
  OpenAlex + Semantic Scholar with Europe PMC/Crossref fallback,
  per-paper extraction with quotes checked against abstracts, cited
  synthesis. Live: 291.5s for 3 papers, real DOIs.
- Move 2 - Verifiable citations (`POST /api/v1/citations/verify`,
  `GET /api/v1/citations/papers/badges`): nomic-embed-text cosine,
  threshold calibrated live to 0.70; retracted / OA / peer-reviewed /
  preprint flags from OpenAlex.
- Move 3 - OA full-text bridge. Move 4 - free PRISMA systematic
  review (`POST /api/v1/review/prisma`).
- Move 5 - Citation graph + gap finder (`POST /api/v1/gap-finder/graph`,
  `/citation-graph` page). Live 2026-11-14: DOI 10.1038/nature12373 gave
  19 nodes, 18 edges, 4 LLM questions in 150.7s.
- Move 6 - Cross-project private knowledge graph
  (`/api/v1/library/*`, Zotero import). All state local in
  `backend/data/library/<user>.json`.
- Move 7 - Transparent model picker (`GET/POST /api/v1/models`) and
  cost meter (`GET /api/v1/usage`, total spent always $0.00, cloud
  price shown at the GPT-4o-mini rate for comparison).
- Move 8 - Honest drafting: extraction table per source paper,
  unsupported-claim highlighter (`sentence_support`,
  `support_summary`), pre-export check (`POST /api/v1/draft/check`)
  that blocks export when any cited paper is retracted.

### Railway readiness (2026-11-14, local, nothing deployed)

Railway is the chosen host. The repo is ready for a dashboard deploy;
see `docs/DEPLOYMENT.md` for the Railway section.

- `railway.json` at the root (backend: Dockerfile builder,
  `backend/Dockerfile`, uvicorn on `$PORT`, healthcheck `/health`),
  `frontend/railway.json` (nginx serves the Vite build on `$PORT`),
  `ollama/railway.json` + `ollama/Dockerfile` + `ollama/entrypoint.sh`
  (official `ollama/ollama` image, listens on `0.0.0.0:11434` for the
  private network, pulls `qwen2.5:3b` and `nomic-embed-text` on first
  boot into the volume at `/root/.ollama`, no public domain).
- `backend/Dockerfile` builds from the repo root and reads `$PORT`
  (shell-form CMD, default 8000); `docker-compose.yml` backend build
  updated to match; `.dockerignore` keeps secrets and local state out
  of images.
- `frontend/Dockerfile` declares `VITE_SUPABASE_URL` and
  `VITE_SUPABASE_ANON_KEY` as build args (Railway passes matching
  service variables into Dockerfile builds) and rewrites nginx's
  listen port to `$PORT` at container start.
- Full env-var list for all three services is in
  `docs/DEPLOYMENT.md`: backend `SUPABASE_URL`, `SUPABASE_KEY`,
  `SUPABASE_JWT_SECRET`, `OPENALEX_API_KEY`, `UNPAYWALL_EMAIL`,
  `CORS_ORIGINS`, `BACKEND_API_KEY`, `OLLAMA_BASE_URL` (private URL of
  the Ollama service); frontend `VITE_SUPABASE_URL`,
  `VITE_SUPABASE_ANON_KEY`, `VITE_API_URL` (backend public URL).
- Expected Railway cost (rates checked 2026-11-14): about $100-130/month
  always on for the 3B setup, dominated by the Ollama service's ~8 GB
  RAM at $10/GB/month. More than the $40-75/month VPS path; the
  trade-off is documented in `docs/DEPLOYMENT.md`.

## Measured numbers (live, CPU-only machine, qwen2.5:3b)

- Evaluation (10 questions, 5 real papers): 9 correct, 1 partially correct,
  0 wrong. All 10 calls HTTP 200. Total LLM time about 38 minutes.
- Full-text summary of a 54,556-char Europe PMC paper: HTTP 200 in
  1107.4 s, all four fields populated with accurate content, zero placeholders.
- Search: 1.0-2.8 s per source. Abstract-based summary: 66-109 s.
  Full-PDF summary: 10-18 minutes per paper on CPU.
- Backend unit tests: 156/156 pass (2026-11-14, 6.1s). Frontend lint:
  7 problems (0 errors, 7 warnings), same 7 pre-existing warnings as
  before moves 7-8. Frontend build passes (13.4s).
- Live verification 2026-11-14 on branch `competitor-moves-7-8`
  (Ollama 0.40.16 reinstalled after a VM restart wiped the binary;
  models survived in `~/.ollama`): `/health` 200, `/ready` 200
  (`ollama: true`), `GET /api/v1/models` 200 (qwen2.5:3b and
  nomic-embed-text listed, active chat qwen2.5:3b), `GET /api/v1/usage`
  200 (total spent $0.00), abstract summarize 200 in 91.0s, RAG ask
  200 in 45.5s with a signed test JWT (401 without token), Deep Review
  200 in 145.4s (max 2 papers, cited synthesis with 2 studies).
  Backend stopped afterwards; Ollama left running.
- The old README performance numbers (1.8 s first results, 6-9 s full
  results, 38% dedup, RAG 74%/18%/8%) were removed: they were never measured.

## Still open

- **Moves 7-8 PR**: implemented and verified locally on branch
  `competitor-moves-7-8`; the only remaining step is the user tapping
  the GitHub approval card so the branch can be pushed and the PR
  opened and merged. Nothing was pushed.
- **Railway deploy**: the repo is ready, but no Railway account,
  project, or service exists yet. The deploy is a dashboard job:
  create the project from the GitHub repo, add the three services
  (Ollama first), set the variables listed in `docs/DEPLOYMENT.md`,
  attach the Ollama volume, generate public domains for backend and
  frontend only. No Railway CLI, config, or token exists in this
  environment.
- **OpenAlex API key**: requested with a free key and activated by the
  user 2026-11-13; live re-test passed (keyed request 200, service
  search 200, badges 200, Deep Review 200). The key lives only in the
  local `backend/.env` as `OPENALEX_API_KEY` (gitignored, never
  committed). Activation link expiry 2026-11-20 no longer matters.
- **UNPAYWALL_EMAIL**: set locally (2026-11-13) to the user's Gmail in
  `backend/.env` (gitignored, never committed) and verified live: a DOI
  lookup now returns real open-access data instead of HTTP 422. Note:
  the service previously read `os.getenv` directly, which missed
  `backend/.env`; it now reads the value through Settings, so the
  `backend/.env` file works. Deployments still need the variable set in
  their own environment. The placeholder default remains unusable.
- **Supabase key rotation**: a new publishable anon key was created
  and set in the local `frontend/.env`, but the old legacy anon JWT is
  still valid; fully invalidating it needs a JWT-secret rotation,
  which would also change the service_role key and was not done. A
  deliberate decision, not part of this deploy. The old legacy anon
  JWT is also still visible in 8 git-history commits; purging
  `frontend/.env` from history is destructive and has not been done.
- **Docker build/run**: the Dockerfiles and Compose file have not been
  built or run (no Docker on the machine used for this work). The
  Railway Dockerfiles are written from Railway's documented behavior
  (Dockerfile builder, `ARG` for build-time variables, `$PORT` at
  runtime) and need a first live build on Railway to confirm.
- **MS application details**: target countries/programs and application
  deadlines have not been decided yet. These decide whether the demo or a
  written paper comes first. Deferred by the user 2026-11-13: build the
  world-class product first.
- **Zotero sync**: Move 6 ships Zotero import; full two-way Zotero
  sync is still open.
