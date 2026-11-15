# Deployment guide - ReSearch Flow

How to ship ReSearch Flow live for real researchers. Last updated 2026-11-14.
Railway is the chosen host (user decision 2026-11-13). Nothing is
deployed yet: the repo is Railway-ready (see below), the deploy itself
is a dashboard job. No Railway CLI, config, or token exists in this
environment, so nothing here executes a deploy.

## What runs in production

Three pieces, plus one managed service:

| Piece | What it is | Where it runs |
| --- | --- | --- |
| Frontend | React + Vite app, built once and served by nginx | Host, port 3000 (nginx on 80 inside the container) |
| Backend | FastAPI, serves `/api/v1/*`, `/health`, `/ready` | Host, port 8000 |
| Ollama | Local LLM: `qwen2.5:3b` chat, `nomic-embed-text` embeddings | Host, outside Docker, port 11434 (or 11435) |
| Pinecone | RAG vector store (Starter free tier): 768-dim vectors, one serverless index, per-paper metadata filter | Managed, pinecone.io, AWS us-east-1 |
| Supabase | Auth + Postgres for saved papers, notes, search history | Managed, free tier |

Search is public: anyone can search papers without an account. Summarize,
ask, draft, and chat history require a Supabase login; the backend verifies
the Supabase JWT on every call and scopes chat sessions to the user.

## Host requirements

Minimum for the default 3B model:

- 4 vCPU, 8 GB RAM, 40 GB disk. The 3B model needs about 2 GB RAM when
  loaded; the backend, frontend, and OS need the rest. Below 8 GB the
  model load fails or the host swaps and every answer takes minutes.
- 8 vCPU, 16 GB RAM if you switch to the 7B model (`OLLAMA_CHAT_MODEL`
  `qwen2.5:7b`) or expect more than a few concurrent users.
- Ubuntu 22.04 or 24.04 LTS, Docker Engine + Docker Compose v2, and
  Ollama installed on the host (not in a container).
- One public IPv4 address and a domain name for HTTPS. Do not ship on
  plain HTTP: Supabase auth cookies and login tokens travel over it.

Why Ollama stays on the host: the backend talks to Ollama over HTTP and
the model files are 2-4 GB. Running Ollama in its own container works
too, but the host install is simpler to upgrade (`ollama pull`) and
keeps the model cache outside Docker volumes.

## Cost estimate (honest)

Prices checked 2026-11-13 from public rate cards; verify before buying,
because Hetzner raised cloud prices twice in 2026 alone.

- Hetzner Cloud, EU: CPX32 (4 vCPU, 8 GB) about EUR 36/month (about
  $40); CPX42 (8 vCPU, 16 GB) about EUR 70-75/month. The cheaper
  cost-optimized CX/CAX sizes (about EUR 9-11/month for 4 vCPU, 8 GB)
  are usually out of stock.
- Hetzner Cloud, US: CPX31 (4 vCPU, 8 GB) about $73/month; CPX41
  (8 vCPU, 16 GB) about $141/month. US prices run roughly double the EU
  ones for the same size.
- Comparable 4 vCPU / 8 GB VPS elsewhere: roughly $20-40/month
  (Vultr, DigitalOcean regular plans sit in this range; check their
  current pages).
- Domain: about $10-15/year. HTTPS certificate: free via Let's Encrypt.
- Supabase: free tier covers this workload (auth + a small Postgres).
- Pinecone Starter: $0, no credit card (2 GB storage, 2M write units
  and 1M read units per month, 5 indexes, AWS us-east-1 only). The
  RAG vector store lives there; embeddings stay local. Paid Standard
  starts at a $50/month minimum, so stay inside Starter: at 768
  dimensions about 500,000 chunk records fit in 2 GB, far above this
  project's scale, and nothing in the code auto-upgrades.
- Paid LLM APIs: none. The whole point of the Ollama setup is that
  there is no per-token bill.

Realistic total: about $40-75/month for the 3B model on an 8 GB box,
about $70-140/month for the 7B model on a 16 GB box, plus about $1/month
amortized for the domain. A CPU Ollama host is not free at scale: every
concurrent user adds CPU time, and the 3B model answers a full-paper
summary in 2-5 minutes on a shared 4 vCPU box. If usage grows, the next
step is a bigger box or a GPU host, not more tuning.

## Environment variables

Copy the examples and fill in real values. Never commit a filled-in
`.env` file.

Backend (`backend/.env`, see `backend/.env.example`):

| Variable | Required | Notes |
| --- | --- | --- |
| `SUPABASE_URL` | yes | Project URL, e.g. `https://<ref>.supabase.co` |
| `SUPABASE_KEY` | yes | Publishable (anon) key. Used for DB access and as the Auth API key |
| `SUPABASE_JWT_SECRET` | recommended | Project JWT secret (Supabase dashboard, Settings, API). Enables fast local HS256 verification. If unset, every protected call verifies against the Supabase Auth API instead, which is slower and needs outbound network |
| `UNPAYWALL_EMAIL` | yes | A real email address. Unpaywall rejects requests without one |
| `CORS_ORIGINS` | yes | JSON list of the exact frontend origins, e.g. `["https://research.example.com"]`. Localhost defaults are already in the code; production must list the real domain |
| `BACKEND_API_KEY` | no | Legacy shared-key guard, now unused by the JWT routes. Keep unset unless an old client still needs it |
| `OLLAMA_BASE_URL` | yes | `http://127.0.0.1:11434` on the host, or `http://host.docker.internal:11434` from inside the backend container (compose already sets this) |
| `OLLAMA_CHAT_MODEL` | no | Default `qwen2.5:3b` |
| `OLLAMA_EMBED_MODEL` | no | Default `nomic-embed-text` |
| `CORE_API_KEY` | no | Only if CORE search is wanted; without it CORE returns no results |
| `SEMANTIC_SCHOLAR_API_KEY` | no | Optional; without it Semantic Scholar is rate-limited to 100 requests per 5 minutes |
| `OPENALEX_API_KEY` | recommended | Free OpenAlex API key (one per email, requested at api.openalex.org). Without it, OpenAlex requests draw on the shared-IP daily budget, which is often used up. While the key is pending activation, requests with it get 403 `key_not_activated` and the backend retries once without the key, so the app keeps working. Click the activation link in the key-request email to activate it |
| `PINECONE_API_KEY` | yes (for RAG chat) | Free Starter API key from pinecone.io (no credit card). Without it, RAG chat answers a clear "Pinecone is not configured" error; search still works, but ask-about-paper, the full-text bridge index step, and Deep Review retrieval need the store |
| `PINECONE_INDEX_NAME` | no | Default `research-flow`. The backend creates the index on first use if it does not exist |
| `PINECONE_CLOUD` | no | Default `aws`. Starter runs on AWS us-east-1 only, so do not change this unless you are on a paid plan |
| `PINECONE_REGION` | no | Default `us-east-1`. Same Starter limit as above |
| `RATE_LIMIT_SUMMARIZE_PER_MINUTE` | no | Default 10 per IP |
| `RATE_LIMIT_CHAT_PER_MINUTE` | no | Default 20 per IP |
| `RATE_LIMIT_DRAFT_PER_HOUR` | no | Default 2 per IP |

Frontend (build-time, see `frontend/.env.example`):

| Variable | Required | Notes |
| --- | --- | --- |
| `VITE_SUPABASE_URL` | yes | Same Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | yes | Same publishable key as the backend |
| `VITE_API_URL` | no | Default `/api/v1`; nginx proxies `/api/` to the backend, so leave it unset in Docker |

## Pinecone setup (free Starter tier)

RAG chat stores its vectors in Pinecone. Embeddings are computed
locally with nomic-embed-text (768 dim); only the vectors leave the
machine. Setup takes about two minutes:

1. Create a free account at pinecone.io and copy an API key from the
   dashboard (no credit card needed for Starter).
2. Put it in `backend/.env` as `PINECONE_API_KEY=<key>`. Never commit
   the real key.
3. Start the backend. On the first RAG call it creates the index
   `research-flow` itself if it does not exist: serverless, AWS
   us-east-1, 768 dimensions, cosine similarity. You do not need to
   create the index by hand, and you must not create it with a
   different dimension: the vectors are 768-dim and a mismatch fails
   every upsert.

Starter limits to stay inside: 2 GB storage, 2M write units and 1M
read units per month, 5 indexes, 100 namespaces per index, AWS
us-east-1 only. One indexed paper is a few hundred vectors; at 768
dimensions about 500,000 chunk records fit in 2 GB, so this project
will not come close. Paid Standard starts at a $50/month minimum:
the code never upgrades on its own, so the only way to get a bill is
to change the plan in the Pinecone dashboard yourself.

Without the key, RAG chat fails with a clear "Pinecone is not
configured" error. The cross-paper library ask
(`POST /api/v1/library/ask`) is unaffected: it still uses a local
FAISS index over saved abstracts and notes.

## Deploy on Railway (chosen host)

Railway is the chosen host. Nothing is deployed yet: the repo is
Railway-ready, the deploy itself is a dashboard job. Config as code
lives in the repo: `railway.json` at the root (backend),
`frontend/railway.json`, `ollama/railway.json`. Railway reads the
config file at each service's Root Directory, so set the root
directory per service as below.

### Services (three, one project)

1. **Backend** - new service from the GitHub repo, Root Directory:
   repo root (the default, do not change). The root `railway.json`
   applies: Dockerfile builder, `backend/Dockerfile`, start command
   `uvicorn` on `$PORT`, healthcheck `/health`. Generate a public
   domain (Settings, Networking).
2. **Frontend** - same repo, second service, Root Directory:
   `frontend`. `frontend/railway.json` applies: Dockerfile builder,
   nginx serves the Vite build and listens on `$PORT`. Generate a
   public domain.
3. **Ollama** - same repo, third service, Root Directory: `ollama`.
   `ollama/railway.json` applies: builds `ollama/Dockerfile` (from
   the official `ollama/ollama` image, plus an entrypoint that pulls
   the models on first boot). Do NOT generate a public domain: the
   Ollama API has no auth. Attach a Volume mounted at `/root/.ollama`
   (this is where models live, about 2.3 GB for the two models).
   One replica only: a volume cannot attach to multiple replicas.

Create the Ollama service first: its first boot pulls about 2.2 GB
of models and takes several minutes. Then the backend, then the
frontend (the frontend build needs the backend's public URL).

### Environment variables

Backend service (Variables tab). Values come from the local
`backend/.env`, never from a committed file:

- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_JWT_SECRET`,
  `OPENALEX_API_KEY`, `UNPAYWALL_EMAIL`, `CORS_ORIGINS`,
  `PINECONE_API_KEY` (required for RAG chat),
  `BACKEND_API_KEY` (optional, legacy shared-key guard).
- `OLLAMA_BASE_URL=http://ollama.railway.internal:11434` - replace
  `ollama` with the Ollama service's actual name if you name it
  differently; port 11434 is Ollama's listen port inside its
  container. Private-network traffic between the services is not
  billed for egress.
- Optional: `OLLAMA_CHAT_MODEL` (default `qwen2.5:3b`),
  `OLLAMA_EMBED_MODEL` (default `nomic-embed-text`), `CORE_API_KEY`,
  `SEMANTIC_SCHOLAR_API_KEY`, `RATE_LIMIT_SUMMARIZE_PER_MINUTE` /
  `RATE_LIMIT_CHAT_PER_MINUTE` / `RATE_LIMIT_DRAFT_PER_HOUR`,
  `UPSTASH_REDIS_REST_URL` + `UPSTASH_REDIS_REST_TOKEN` (persistent
  chat sessions; without them sessions clear on backend restart).
- `CORS_ORIGINS`: JSON list with the frontend's Railway public URL,
  e.g. `["https://<frontend>.up.railway.app"]`. Set this AFTER
  generating the frontend domain, then redeploy the backend.

Frontend service (Variables tab). These are build-time: Vite bakes
`VITE_*` into the bundle, and the Dockerfile declares each as an
`ARG` so Railway passes the service variable into the build.
Changing one needs a rebuild (redeploy), not just a restart:

- `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` - same Supabase
  project as the backend; the anon key is publishable by design.
- `VITE_API_URL=https://<backend>.up.railway.app/api/v1` - the
  backend's public domain. Set this AFTER generating the backend
  domain, then redeploy the frontend.
- The frontend's nginx `/api/` proxy (used by docker compose) is
  unused on Railway: the browser calls the backend public URL
  directly.

Ollama service: no variables needed. `OLLAMA_HOST` is already set to
`0.0.0.0:11434` in `ollama/Dockerfile` so the private network can
reach it.

### Model pull step

Automatic. `ollama/entrypoint.sh` starts `ollama serve`, waits for
it, then runs `ollama pull qwen2.5:3b` and
`ollama pull nomic-embed-text` for any model not already on the
volume. First boot takes several minutes (about 2.2 GB download).
Check the Ollama service logs for "Ollama ready with models" and
confirm with the backend's `/ready` (`ollama: true`) or
`GET /api/v1/models` on the backend, which should list both models.
If a model ever needs re-pulling, redeploy the service with the
volume attached: the pull is skipped when the model is already on
the volume.

### Expected cost (Railway, usage-based)

Rates checked 2026-11-14 from Railway's pricing page; verify before
committing, Railway changes prices. Hobby is $5/month and includes
$5 of usage; Pro is $20/month and includes $20. Past that: $20 per
vCPU per month, $10 per GB of RAM per month, $0.15 per GB of volume
storage per month, $0.05 per GB of public egress. Metered per second
on actual use; private-network traffic is not billed.

- The Ollama service dominates the bill: the 3B model needs about
  8 GB RAM, which is about $80/month in RAM alone at $10/GB/month,
  plus its CPU while inference runs. Hobby caps a single replica at
  8 vCPU / 8 GB, which is exactly the 3B model's size: it fits, with
  no headroom for the 7B model (that needs Pro and about 16 GB, about
  $160/month in RAM alone).
- Backend + frontend are small (well under 1 GB RAM each when idle):
  roughly $10-20/month each in RAM plus a little CPU.
- Realistic total for the 3B setup, always on: about $100-130/month.
  That is more than the $40-75/month VPS estimate in the compose
  section below: Railway charges for the RAM the model holds, a VPS
  charges a flat box price. If that is too much, the cheaper ship is
  the VPS path below, or stop the Ollama service when nobody is using
  it (usage is metered, so stopped is not billed; the models stay on
  the volume).
- Volume: about 2.3 GB of models at $0.15/GB/month is under
  $0.50/month.

### Verify after deploy

- Backend: `https://<backend>.up.railway.app/health` returns
  `{"status":"healthy"}`; `/ready` returns `{"status":"ready",
  "ollama":true}` (`degraded` + `ollama:false` means the Ollama
  service or `OLLAMA_BASE_URL` is wrong).
- Backend: `GET https://<backend>.up.railway.app/api/v1/models`
  lists `qwen2.5:3b` and `nomic-embed-text`.
- Frontend: open the frontend URL, search works without login; login
  works (add the frontend Railway domain to the Supabase redirect
  URLs: Supabase dashboard, Authentication, URL Configuration).
- Protected route without token: `POST /api/v1/chat/ask` with no
  token returns 401.

### Known limits on Railway

- CPU inference is slow: abstract summaries about 1-2 minutes,
  full-paper summaries minutes (2-5 on a 4 vCPU box; Railway CPU is
  shared, expect the slow end). Deep Review with 5 papers takes
  several minutes. The frontend shows progress; it does not hang
  silently.
- The backend is a single process with no worker pool; one heavy
  request uses the whole CPU model. Rate limits (10 summarize/min,
  20 chat/min, 2 drafts/hour per IP) still apply.
- Railway volumes attach to one replica only: keep all three
  services at 1 replica.
- The Ollama service has no public domain and no healthcheck in
  `ollama/railway.json` on purpose: it is a private-only service,
  and the backend `/ready` endpoint is the real check.
- Hobby plan: 5 GB total volume storage across the project; the
  models use about 2.3 GB, which fits. Pro allows up to 1 TB.

## Deploy steps (Docker Compose)

1. Create the host (4 vCPU, 8 GB minimum) and point the domain at it.
2. Install Docker Engine and the Compose plugin, and Ollama:
   `curl -fsSL https://ollama.com/install.sh | sh`
3. Pull the models (about 2.2 GB total):
   `ollama pull qwen2.5:3b` and `ollama pull nomic-embed-text`
   Then `ollama serve` (systemd service if available) and check
   `curl http://127.0.0.1:11434/api/tags` lists both models.
4. Clone the repo and create `backend/.env` from
   `backend/.env.example` with real values. The frontend needs no
   `.env` file in Docker; `VITE_API_URL` defaults to `/api/v1`.
5. Set `CORS_ORIGINS` to the exact production domain. The backend
   rejects browser calls from any other origin.
6. Start everything: `docker compose up --build -d`
7. Verify from the host:
   - `curl http://127.0.0.1:8000/health` returns `{"status":"healthy"}`
   - `curl http://127.0.0.1:8000/ready` returns `{"status":"ready"}`
     (503 with `ollama: false` means Ollama is not reachable; fix step 3)
   - `curl http://127.0.0.1:3000/` returns the frontend HTML
   - `curl "http://127.0.0.1:8000/api/v1/arxiv/search?query=test&limit=1"`
     returns a paper (public search, no login needed)
   - `curl -X POST http://127.0.0.1:8000/api/v1/chat/ask -d '{}'`
     returns 401 (protected route, no token)
8. Put nginx or Caddy in front of ports 3000 and 8000 with HTTPS
   (Let's Encrypt). The compose setup exposes plain HTTP on localhost
   only by design; TLS termination is the operator's job.
9. In the Supabase dashboard, add the production domain to the
   Auth redirect URLs (Authentication, URL Configuration), or login
   redirects will fail.

## What is still manual

- Railway is the chosen host. The Railway account, the project, and
  the three dashboard services above still need creating (no Railway
  CLI, config, or token exists in this environment, so the deploy is
  a dashboard job, not something this repo can run).
- TLS termination and the domain's DNS records.
- Supabase redirect URLs for the production domain (step 9).
- The old legacy Supabase anon JWT is still valid. Rotating the
  JWT secret invalidates it, but also changes the service_role key,
  so that rotation is a deliberate decision, not part of this deploy.
- If the Supabase project ever migrates from HS256 to ES256 signing
  keys, unset `SUPABASE_JWT_SECRET` so the backend falls back to
  Auth API verification; HS256 verification rejects ES256 tokens.
- Backups: Supabase handles the database. The host itself needs no
  backup beyond the `.env` file, which should be stored somewhere
  safe off the host (it holds the keys).

## Known limits in production

- One user can still use the whole CPU model: rate limits are
  10 summarize/min, 20 chat/min, 2 drafts/hour per IP. Tune them in
  the environment if real abuse shows up.
- Full-paper summaries take 2-5 minutes on a 4 vCPU box with the
  3B model; abstract summaries take about 1-2 minutes. The frontend
  shows a progress state, it does not hang silently.
- The backend is a single process with no worker pool. If it goes
  down, `/health` fails and the frontend shows the "AI backend is
  currently unavailable" banner. Restart it with
  `docker compose restart backend`.
- Chat history lives in Redis when configured, otherwise in memory:
  a backend restart clears in-memory sessions. Set
  `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` for
  persistent sessions.
