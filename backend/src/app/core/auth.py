"""Minimal API-key check for state-changing backend routes.

Save-article and notes writes do not go through this backend at all:
the frontend calls Supabase directly with the logged-in user's own
JWT, and row-level security scopes rows to that user, so there is no
backend route to protect there.

The backend's POST routes (extract / summarize / ask / draft /
citation network / chat ask) are anonymous compute endpoints the
frontend calls with no credential of any kind. Gating them with a
shared key would break the frontend until it is changed to send the
key, so they are deliberately left open here.

This dependency therefore guards only the one backend route whose
sole purpose is destroying state: DELETE /chat/history/{session_id},
which today lets anyone wipe any session's Redis history by UUID.
The check is optional when BACKEND_API_KEY is unset, so local dev
and the current frontend flow keep working unchanged. When the key
is set, requests without a matching X-API-Key header get 401.

What still needs a proper auth design (not done here):
- Verify the Supabase JWT (Authorization: Bearer <access token>)
  on the backend for every state-changing or user-scoped call, and
  scope chat sessions to the authenticated user instead of a bare
  client-supplied UUID. That needs the frontend to send its session
  access token on every fetch, plus a live Supabase project to test
  against, so it is a frontend + backend change, not a one-line fix.
- GET /search/fetch also writes: it queues a background job that
  stores fetched papers in Supabase/Neo4j with the server key. It
  is a read endpoint the frontend calls unauthenticated, so it was
  left ungated; a per-user rate limit or JWT check belongs there
  once the Supabase JWT design above lands.
"""

import secrets

from fastapi import Header, HTTPException

from .config import settings


async def verify_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Allow the request when no key is configured (local dev).

    When BACKEND_API_KEY is set, require a matching X-API-Key header.
    """
    expected = settings.BACKEND_API_KEY
    if not expected:
        return None
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=401, detail="Invalid or missing X-API-Key header"
        )
    return None
