"""Provider-agnostic LLM interface + resilience helpers.

The interface is deliberately tiny: text in, text out. Anything provider-specific
(JSON mode, tools, safety settings) stays inside the concrete provider so /ask
never depends on which LLM is behind it.

This module also owns the cross-provider resilience policy — retry transient
errors with backoff, fail fast on quota, fall back across models — so every
provider gets the same behavior and it can be unit-tested without a network.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Callable

logger = logging.getLogger("cinemind.llm")


# ---------------------------------------------------------------------------
# Errors surfaced to callers. Endpoints catch LLMError and degrade gracefully
# (a clear 503) instead of leaking a provider exception as a raw 500.
# ---------------------------------------------------------------------------
class LLMError(Exception):
    """Base class for LLM failures meant to be handled by callers."""


class LLMUnavailableError(LLMError):
    """Every candidate model failed with a transient or quota error."""


class LLMConfigError(LLMError):
    """A non-recoverable configuration error (e.g. an invalid API key)."""


# Error buckets that decide retry/fallback behavior.
QUOTA, TRANSIENT, FATAL, OTHER = "quota", "transient", "fatal", "other"


def classify_error(exc: BaseException) -> str:
    """Bucket a provider/SDK exception:

    - QUOTA     (429 / RESOURCE_EXHAUSTED): the model is rate/quota limited. No
      retry — but a *different* model has its own quota, so fall back.
    - TRANSIENT (5xx / UNAVAILABLE / timeout / connection): retry with backoff.
    - FATAL     (401/403 / invalid key): config problem; retrying won't help.
    - OTHER     (anything else, e.g. an unknown model id): no retry, try fallback.
    """
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    name = type(exc).__name__.lower()
    msg = str(exc).lower()

    if code == 429 or "resource_exhausted" in msg or "quota" in msg:
        return QUOTA
    if (
        code in (500, 502, 503, 504)
        or "unavailable" in msg
        or "timeout" in name
        or "timeout" in msg
        or "connecterror" in name
        or "connectionerror" in name
    ):
        return TRANSIENT
    if (
        code in (401, 403)
        or "api_key_invalid" in msg
        or "api key not valid" in msg
        or "permission_denied" in msg
        or "unauthenticated" in msg
    ):
        return FATAL
    return OTHER


def run_with_resilience(
    call: Callable[[str], str],
    models: list[str],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Run ``call(model)`` across ``models`` with a resilience policy.

    For each model: retry TRANSIENT errors up to ``max_attempts`` with exponential
    backoff; on QUOTA stop immediately (no retry) and move to the next model; on
    FATAL raise ``LLMConfigError`` (no fallback — it won't help). When a model is
    exhausted, fall back to the next. If all models fail, raise
    ``LLMUnavailableError``.
    """
    last_exc: BaseException | None = None
    for model in models:
        for attempt in range(1, max_attempts + 1):
            try:
                return call(model)
            except LLMError:
                raise  # already classified upstream; don't re-wrap
            except Exception as exc:  # noqa: BLE001 — provider/SDK exceptions vary
                last_exc = exc
                kind = classify_error(exc)
                if kind == FATAL:
                    raise LLMConfigError(str(exc)) from exc
                if kind == TRANSIENT and attempt < max_attempts:
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "LLM transient error on %s (attempt %d/%d): %s; retrying in %.1fs",
                        model, attempt, max_attempts, type(exc).__name__, delay,
                    )
                    sleep(delay)
                    continue
                logger.warning(
                    "LLM %s error on %s: %s; falling back to next model",
                    kind, model, type(exc).__name__,
                )
                break  # quota / exhausted-transient / other -> next model
    raise LLMUnavailableError(
        f"all LLM models failed ({', '.join(models)}): {last_exc}"
    ) from last_exc


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Return the model's text response to `user`, guided by `system`."""
        ...
