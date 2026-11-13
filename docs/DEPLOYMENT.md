# Deployment guide - ReSearch Flow

How to ship ReSearch Flow live for real researchers. Last updated 2026-11-13.
Nothing here is deployed yet: this guide prepares the ship, it does not
execute it. A hosting account and a host choice are still needed.

## What runs in production

Three pieces, plus one managed service:

| Piece | What it is | Where it runs |
| --- | --- | --- |
| Frontend | React + Vite app, built once and served by nginx | Host, port 3000 (nginx on 80 inside the container) |
| Backend | FastAPI, serves `/api/v1/*`, `/health`, `/ready` | Host, port 8000 |
| Ollama | Local LLM: `qwen2.5:3b` chat, `nomic-embed-text` embeddings | Host, outside Docker, port 11434 (or 11435) |
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
| `RATE_LIMIT_SUMMARIZE_PER_MINUTE` | no | Default 10 per IP |
| `RATE_LIMIT_CHAT_PER_MINUTE` | no | Default 20 per IP |
| `RATE_LIMIT_DRAFT_PER_HOUR` | no | Default 2 per IP |

Frontend (build-time, see `frontend/.env.example`):

| Variable | Required | Notes |
| --- | --- | --- |
| `VITE_SUPABASE_URL` | yes | Same Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | yes | Same publishable key as the backend |
| `VITE_API_URL` | no | Default `/api/v1`; nginx proxies `/api/` to the backend, so leave it unset in Docker |

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

- The hosting account and the host choice. No account exists yet.
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
