"""Supabase JWT verification for protected backend routes.

Public search stays public: any researcher can search papers without
logging in. The routes that cost CPU or touch a user's own data
require a logged-in user:

- POST /chat/ask, GET /chat/history/{session_id},
  DELETE /chat/history/{session_id} - chat sessions are scoped to the
  authenticated user, so one user cannot read or wipe another user's
  history by guessing a session UUID.
- POST /draft/generate - draft generation takes minutes of CPU.

How verification works (two paths, first one that applies wins):

1. Local HS256 verification when SUPABASE_JWT_SECRET is set. This
   project predates Supabase's ES256 signing keys, so its JWKS
   endpoint returns an empty key set and JWKS verification cannot
   work here. Its access tokens are HS256 JWTs signed with the
   project's legacy JWT secret. PyJWT checks signature, expiry,
   audience ("authenticated") and issuer
   (<SUPABASE_URL>/auth/v1). No network call.
2. Supabase Auth API fallback when no secret is configured:
   GET <SUPABASE_URL>/auth/v1/user with the apikey header and the
   user's token. The Auth API validates the token server-side and
   returns the user. Results are cached in memory for
   AUTH_CACHE_TTL_SECONDS so a chat turn does not pay a network
   round trip on every call.

When neither SUPABASE_URL nor SUPABASE_KEY is configured, protected
routes answer 503 (auth not configured) instead of failing open.
"""

import hashlib
import logging
import time

import httpx
import jwt
from fastapi import Header, HTTPException

from .config import settings

logger = logging.getLogger(__name__)

# token sha256 -> (verified_at_epoch, user_dict)
_verified_cache: dict[str, tuple[float, dict]] = {}


def _auth_base_url() -> str:
    return settings.SUPABASE_URL.rstrip("/")


def _verify_local_hs256(token: str) -> dict:
    """Verify a Supabase access token locally with the JWT secret."""
    payload = jwt.decode(
        token,
        settings.SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        audience=settings.SUPABASE_JWT_AUDIENCE,
        issuer=_auth_base_url() + "/auth/v1",
        options={"require": ["exp", "sub"]},
    )
    user_id = payload.get("sub")
    if not user_id:
        raise jwt.InvalidTokenError("Token has no sub claim")
    return {
        "id": user_id,
        "email": payload.get("email"),
        "role": payload.get("role", "authenticated"),
    }


def _verify_via_auth_api(token: str) -> dict:
    """Verify a token through the Supabase Auth API (GET /auth/v1/user)."""
    cache_key = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = time.time()
    cached = _verified_cache.get(cache_key)
    if cached and now - cached[0] < settings.AUTH_CACHE_TTL_SECONDS:
        return cached[1]
    try:
        resp = httpx.get(
            _auth_base_url() + "/auth/v1/user",
            headers={
                "apikey": settings.SUPABASE_KEY,
                "Authorization": "Bearer " + token,
            },
            timeout=10,
        )
    except httpx.HTTPError as e:
        logger.warning("Supabase Auth API unreachable: %s", e)
        raise HTTPException(
            status_code=503, detail="Authentication service unavailable"
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=401, detail="Invalid or expired login token"
        )
    data = resp.json()
    user_id = data.get("id")
    if not user_id:
        raise HTTPException(
            status_code=401, detail="Invalid or expired login token"
        )
    user = {
        "id": user_id,
        "email": data.get("email"),
        "role": data.get("role", "authenticated"),
    }
    _verified_cache[cache_key] = (now, user)
    return user


def verify_supabase_jwt(token: str) -> dict:
    """Verify a Supabase access token and return the user.

    Raises 503 when auth is not configured, 401 when the token is
    missing, invalid or expired.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured on this server",
        )
    if settings.SUPABASE_JWT_SECRET:
        try:
            return _verify_local_hs256(token)
        except jwt.PyJWTError as e:
            # A token that fails local verification is rejected here,
            # not passed to the Auth API: a bad signature or expired
            # token is invalid, full stop. Note the one exception to
            # this rule: if the Supabase project later migrates to
            # ES256 signing keys, HS256 verification will reject its
            # tokens, so unset SUPABASE_JWT_SECRET at that point and
            # let the Auth API path verify them instead.
            logger.info("Local JWT verification failed: %s", e)
            raise HTTPException(
                status_code=401, detail="Invalid or expired login token"
            )
    return _verify_via_auth_api(token)


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> dict:
    """FastAPI dependency: the logged-in user, or 401 / 503."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header. Log in to use this feature.",
        )
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header. Log in to use this feature.",
        )
    return verify_supabase_jwt(token)


def scoped_session_id(user_id: str, session_id: str) -> str:
    """Scope a client-supplied session id to one user.

    Chat history is stored under this key, so a session UUID only
    ever resolves inside its owner's namespace.
    """
    return f"{user_id}:{session_id}"
