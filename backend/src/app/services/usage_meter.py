"""
Usage meter: transparent cost meter (Move 7).

Every local LLM task (summarize, ask, draft, deep review, prisma)
records one line in a lightweight local JSONL log under
backend/data/usage_log.jsonl (gitignored, never committed). Each
line holds the task, model, prompt/generated token estimates and
wall time. Token counts are estimates (about 4 characters per token)
unless the caller supplies real counts, and the response says so.

Cloud price avoided: what the same tokens would have cost on a
published cloud rate - GPT-4o-mini at $0.15 per 1M input tokens and
$0.60 per 1M output tokens (OpenAI pricing page, openai.com/api/
pricing, accessed 2026-11-14). Total spent is always $0.00 because
every call runs on the local Ollama server.
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# GPT-4o-mini published pricing, USD per 1M tokens.
# Source: OpenAI pricing page (openai.com/api/pricing), accessed 2026-11-14.
CLOUD_RATE_NAME = "GPT-4o-mini"
CLOUD_RATE_INPUT_PER_MILLION = 0.15
CLOUD_RATE_OUTPUT_PER_MILLION = 0.60
CLOUD_RATE_SOURCE = "OpenAI pricing page (openai.com/api/pricing), accessed 2026-11-14"

TASKS = ("summarize", "ask", "draft", "deep_review", "prisma")


def _log_path() -> Path:
    override = os.environ.get("RESEARCH_FLOW_USAGE_LOG_PATH")
    if override:
        return Path(override)
    return BASE_DIR / "data" / "usage_log.jsonl"


def estimate_tokens(text: str) -> int:
    """Rough token estimate: about 4 characters per token."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def record_usage(
    task: str,
    model: str = "",
    prompt_tokens: Optional[int] = None,
    generated_tokens: Optional[int] = None,
    prompt_chars: int = 0,
    output_chars: int = 0,
    seconds: float = 0.0,
) -> Optional[Dict[str, object]]:
    """Append one usage line. Never raises: metering must not break a task."""
    try:
        if task not in TASKS:
            task = "summarize"
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "task": task,
            "model": model or "",
            "prompt_tokens": int(prompt_tokens) if prompt_tokens is not None else estimate_tokens("x" * prompt_chars),
            "generated_tokens": int(generated_tokens) if generated_tokens is not None else estimate_tokens("x" * output_chars),
            "seconds": round(float(seconds or 0.0), 2),
            "estimated": prompt_tokens is None or generated_tokens is None,
        }
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        return entry
    except Exception as e:
        logger.warning("Usage recording failed (task kept running): %s", e)
        return None


def record_llm_call(task: str, model: str, prompt_text: str, output_text: str, seconds: float) -> Optional[Dict[str, object]]:
    """Convenience wrapper: token estimates from prompt/output text."""
    return record_usage(
        task=task,
        model=model or "",
        prompt_chars=len(prompt_text or ""),
        output_chars=len(output_text or ""),
        seconds=seconds,
    )


def _read_entries() -> List[Dict[str, object]]:
    path = _log_path()
    entries: List[Dict[str, object]] = []
    try:
        if not path.exists():
            return entries
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict) and entry.get("task"):
                entries.append(entry)
    except Exception as e:
        logger.warning("Could not read usage log: %s", e)
    return entries


def cloud_price_avoided_usd(prompt_tokens: int, generated_tokens: int) -> float:
    """What these tokens would have cost at the GPT-4o-mini rate."""
    return round(
        prompt_tokens / 1_000_000 * CLOUD_RATE_INPUT_PER_MILLION
        + generated_tokens / 1_000_000 * CLOUD_RATE_OUTPUT_PER_MILLION,
        6,
    )


def get_usage_summary() -> Dict[str, object]:
    """Aggregate the log per task plus totals and cloud price avoided."""
    entries = _read_entries()
    per_task: Dict[str, Dict[str, object]] = {}
    total_prompt = 0
    total_generated = 0
    total_seconds = 0.0
    for entry in entries:
        task = str(entry.get("task") or "summarize")
        bucket = per_task.setdefault(
            task,
            {"task": task, "calls": 0, "prompt_tokens": 0, "generated_tokens": 0,
             "total_tokens": 0, "seconds": 0.0, "cloud_price_avoided_usd": 0.0},
        )
        prompt_tokens = int(entry.get("prompt_tokens") or 0)
        generated_tokens = int(entry.get("generated_tokens") or 0)
        seconds = float(entry.get("seconds") or 0.0)
        bucket["calls"] = int(bucket["calls"]) + 1
        bucket["prompt_tokens"] = int(bucket["prompt_tokens"]) + prompt_tokens
        bucket["generated_tokens"] = int(bucket["generated_tokens"]) + generated_tokens
        bucket["total_tokens"] = int(bucket["total_tokens"]) + prompt_tokens + generated_tokens
        bucket["seconds"] = round(float(bucket["seconds"]) + seconds, 2)
        total_prompt += prompt_tokens
        total_generated += generated_tokens
        total_seconds += seconds
    for bucket in per_task.values():
        bucket["cloud_price_avoided_usd"] = cloud_price_avoided_usd(
            int(bucket["prompt_tokens"]), int(bucket["generated_tokens"])
        )
    return {
        "total_calls": len(entries),
        "total_prompt_tokens": total_prompt,
        "total_generated_tokens": total_generated,
        "total_tokens": total_prompt + total_generated,
        "total_seconds": round(total_seconds, 2),
        "total_spent_usd": 0.0,
        "cloud_price_avoided_usd": cloud_price_avoided_usd(total_prompt, total_generated),
        "cloud_rate": {
            "model": CLOUD_RATE_NAME,
            "input_usd_per_million_tokens": CLOUD_RATE_INPUT_PER_MILLION,
            "output_usd_per_million_tokens": CLOUD_RATE_OUTPUT_PER_MILLION,
            "source": CLOUD_RATE_SOURCE,
        },
        "token_note": (
            "Token counts are estimates (about 4 characters per token) "
            "unless a call supplied real counts; the cloud price avoided "
            "is computed from those estimates at the rate above."
        ),
        "spent_note": "Total spent is always $0.00: every task runs on the local Ollama server.",
        "by_task": [per_task[task] for task in sorted(per_task)],
    }
