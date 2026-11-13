import json
import os
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from pathlib import Path
from typing import Annotated, Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


def _sanitize_no_proxy() -> None:
    """
    Workaround for an httpx bug: httpx raises InvalidURL on bracketed
    IPv6 entries such as [::1] in NO_PROXY, and the supabase client
    (created at import time by db/client_supabase.py) builds an httpx
    client that parses NO_PROXY. Strip bracketed entries; localhost
    and 127.0.0.1 already cover the local Ollama server. Only the
    process environment is changed, not the system. This runs at
    import time in config.py because config is imported before any
    module that creates an httpx or supabase client.
    """
    for key in ("NO_PROXY", "no_proxy"):
        value = os.environ.get(key)
        if not value:
            continue
        cleaned = ",".join(
            part.strip() for part in value.split(",") if "[" not in part
        )
        if "localhost" not in cleaned:
            cleaned = (cleaned + ",localhost,127.0.0.1") if cleaned else "localhost,127.0.0.1"
        os.environ[key] = cleaned


_sanitize_no_proxy()

class Settings(BaseSettings):
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    # Supabase JWT verification for protected backend routes.
    # Supabase issues HS256 access tokens signed with the project's
    # legacy JWT secret (this project predates the ES256 signing keys,
    # so the JWKS endpoint returns an empty key set). When
    # SUPABASE_JWT_SECRET is set, tokens are verified locally with
    # PyJWT (fast, no network call). When it is unset, verification
    # falls back to the Supabase Auth API (GET /auth/v1/user) using
    # SUPABASE_URL + SUPABASE_KEY. The secret must come from the
    # environment or backend/.env - never hard-code it, never commit
    # it. Without SUPABASE_URL and SUPABASE_KEY, protected routes
    # answer 503 (auth not configured) instead of failing open.
    SUPABASE_JWT_SECRET: Optional[str] = None
    SUPABASE_JWT_AUDIENCE: str = "authenticated"
    # How long a verified token result is cached in memory (seconds).
    # The Auth API fallback makes one network call per uncached token.
    AUTH_CACHE_TTL_SECONDS: int = 60
    # Per-IP rate limits for the expensive LLM endpoints. Draft
    # generation takes minutes of CPU per call, so it is capped hard.
    RATE_LIMIT_SUMMARIZE_PER_MINUTE: int = 10
    RATE_LIMIT_CHAT_PER_MINUTE: int = 20
    RATE_LIMIT_DRAFT_PER_HOUR: int = 2
    # LLM configuration - local Ollama only. No paid LLM APIs.
    # The FYP-era OpenAI / OpenRouter keys are removed on purpose:
    # this is a non-commercial research project and must stay zero-cost.
    # Chat model is chosen by machine: qwen2.5:3b on this dev machine
    # (no GPU, ~6 GB RAM), qwen2.5:7b on a 16 GB laptop (see README).
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11435"
    OLLAMA_CHAT_MODEL: str = "qwen2.5:3b"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_NUM_CTX: int = 8192
    # Optional local vision model for figure analysis (e.g. "llava:7b").
    # None (default) means figure/vision analysis is OFF: figures are
    # still extracted from the PDF, but not analyzed, and the draft
    # says so instead of failing. A vision model needs much more RAM
    # than the 3B chat model, so it is never enabled by default.
    OLLAMA_VISION_MODEL: Optional[str] = None
    CORE_API_KEY: Optional[str] = None
    SEMANTIC_SCHOLAR_API_KEY: Optional[str] = None

    # Upstash Redis Configuration
    UPSTASH_REDIS_REST_URL: Optional[str] = None
    UPSTASH_REDIS_REST_TOKEN: Optional[str] = None
    REDIS_CHAT_TTL: int = 3600  # 1 hour TTL for chat sessions

    # Neo4j Configuration
    # NEO4J_PASSWORD has no default: set it in the environment.
    # The old hardcoded default ("password") was a security flaw.
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    # CORS Configuration
    # Locked down to the local frontend origins by default. Override
    # with a comma-separated CORS_ORIGINS env var (a JSON list also
    # works). "*" is no longer the default: with allow_credentials=True
    # a wildcard origin is rejected by browsers anyway, and it let any
    # site call the API from a logged-in browser.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # Optional shared key for state-changing backend routes
    # (X-API-Key header). When unset, local dev stays open and the
    # frontend flow is unchanged. When set, write routes reject
    # requests without the matching header. This is a stopgap, not
    # user auth: see src/app/core/auth.py.
    BACKEND_API_KEY: Optional[str] = None

    # Contact email sent with Unpaywall requests, as its API requires.
    # Unpaywall rejects example.com addresses with HTTP 422, so the
    # placeholder default below does NOT work live: set a real address
    # in backend/.env (UNPAYWALL_EMAIL) or the environment. This field
    # exists so the value is read through Settings (which loads
    # backend/.env); reading os.getenv directly in the service missed
    # the .env file because pydantic-settings does not export it.
    UNPAYWALL_EMAIL: str = "research-flow@example.com"

    model_config = SettingsConfigDict(
        env_file=[str(BASE_DIR / ".env"), str(BASE_DIR.parent / ".env")],
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()
