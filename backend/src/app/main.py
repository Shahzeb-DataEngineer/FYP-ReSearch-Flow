import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
from src.app.api.v1.api_router import api_router
from src.app.db.client_neo4j import neo4j_client
from src.app.core.config import settings
from src.app.core.rate_limit import check_rate_limit
from src.app.services.llm_provider import check_ollama_available

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    neo4j_client.connect()
    yield
    # Shutdown
    neo4j_client.disconnect()


app = FastAPI(
    title="ReSearch Flow API",
    description="Research paper search and management API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - IMPORTANT for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Reject over-limit LLM calls with 429 before any model work.

    Only paths under the LLM families are limited (see
    src/app/core/rate_limit.py); search and all other routes pass
    through untouched.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method == "POST":
            allowed, retry_after = check_rate_limit(request)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": {
                            "error": "rate_limited",
                            "message": (
                                "Too many AI requests from this address. "
                                "The model runs on CPU and is shared by all "
                                "researchers; please wait a moment and retry."
                            ),
                            "retry_after_seconds": retry_after,
                        }
                    },
                    headers={"Retry-After": str(retry_after)},
                )
        return await call_next(request)


app.add_middleware(RateLimitMiddleware)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Never leak a traceback or internal detail to API clients."""
    logger.error("Unhandled error on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "ReSearch Flow API is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/ready")
def ready_check():
    """Readiness for load balancers and the frontend AI banner.

    Reports whether the local Ollama server answers. The API itself
    can be up while the model is down (Ollama not started, models
    not pulled); in that case search still works but summarize, ask
    and draft fail, and the frontend shows that instead of hanging.
    """
    ollama_ok = check_ollama_available(timeout=3)
    body = {"status": "ready" if ollama_ok else "degraded", "ollama": ollama_ok}
    return JSONResponse(status_code=200 if ollama_ok else 503, content=body)
