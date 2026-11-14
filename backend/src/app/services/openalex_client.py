"""
Shared OpenAlex API-key handling for every OpenAlex caller.

OpenAlex requires an api_key since 2026-02-13; without one, requests
draw on the shared-IP daily budget, which is often already used up.
The key is sent as an ``Authorization: Bearer`` header.

While a key is pending activation, OpenAlex answers HTTP 403 with a
``key_not_activated`` error. Callers must not fail hard on that: they
retry once without the key, so the app works before activation (on the
shared budget) and after it (on the key's own budget). This module
holds the two pieces every caller needs:

- :func:`get_openalex_headers`: the header when a key is configured,
  empty otherwise.
- :func:`is_key_not_activated`: True for a 403 key_not_activated
  response.

The key is read from Settings at call time (``OPENALEX_API_KEY``,
from backend/.env or the environment) so tests can patch it and the
value is never hard-coded. Keep ``requests.get`` calls in the calling
modules (not wrapped here) so existing tests that patch a module's
``requests.get`` keep working.
"""
import logging
from typing import Dict

logger = logging.getLogger(__name__)


def get_openalex_headers() -> Dict[str, str]:
    """Authorization header for OpenAlex when an API key is configured."""
    from ..core.config import settings

    key = (settings.OPENALEX_API_KEY or "").strip()
    if not key:
        return {}
    return {"Authorization": f"Bearer {key}"}


def is_key_not_activated(response) -> bool:
    """True when OpenAlex refused the request because the API key has
    not been activated yet (HTTP 403 with a key_not_activated error).
    """
    if response is None or getattr(response, "status_code", None) != 403:
        return False
    body = ""
    text = getattr(response, "text", None)
    if isinstance(text, str):
        body = text
    if not body:
        try:
            body = str(response.json())
        except Exception:
            body = ""
    return "key_not_activated" in body.lower()
