"""Unit tests for the LLM resilience policy (no network).

We drive run_with_resilience() with a fake `call(model)` whose per-model outcomes
are scripted, so retry/backoff, fail-fast-on-quota, and model fallback are tested
deterministically.
"""

import pytest

from app.llm.base import (
    FATAL,
    QUOTA,
    TRANSIENT,
    LLMConfigError,
    LLMUnavailableError,
    classify_error,
    run_with_resilience,
)


class FakeAPIError(Exception):
    """Stand-in for a provider/SDK error carrying an HTTP-ish status code."""

    def __init__(self, code: int, msg: str = ""):
        super().__init__(msg or f"HTTP {code}")
        self.code = code


def _scripted(script):
    """Return (call, calls): call(model) pops the next outcome for that model;
    an Exception is raised, anything else is returned. `calls` records the order."""
    calls = []

    def call(model):
        calls.append(model)
        outcome = script[model].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return call, calls


_noop_sleep = lambda _delay: None  # noqa: E731


# --------------------------- classification --------------------------------
@pytest.mark.parametrize("code,expected", [
    (429, QUOTA), (503, TRANSIENT), (500, TRANSIENT), (504, TRANSIENT),
    (401, FATAL), (403, FATAL),
])
def test_classify_by_code(code, expected):
    assert classify_error(FakeAPIError(code)) == expected


def test_classify_by_message():
    assert classify_error(Exception("429 RESOURCE_EXHAUSTED")) == QUOTA
    assert classify_error(Exception("503 UNAVAILABLE high demand")) == TRANSIENT
    assert classify_error(Exception("API key not valid")) == FATAL


# --------------------------- retry / fallback ------------------------------
def test_transient_retries_then_succeeds():
    call, calls = _scripted({"m1": [FakeAPIError(503), FakeAPIError(503), "ok"]})
    out = run_with_resilience(call, ["m1"], max_attempts=3, base_delay=0, sleep=_noop_sleep)
    assert out == "ok"
    assert calls == ["m1", "m1", "m1"]  # retried in place


def test_quota_fails_fast_then_falls_back():
    # 429 on the primary -> no retry, immediately try the fallback model.
    call, calls = _scripted({"m1": [FakeAPIError(429)], "m2": ["ok"]})
    out = run_with_resilience(call, ["m1", "m2"], max_attempts=3, base_delay=0, sleep=_noop_sleep)
    assert out == "ok"
    assert calls == ["m1", "m2"]  # m1 tried exactly once


def test_exhausted_transient_falls_back():
    call, calls = _scripted({"m1": [FakeAPIError(503)] * 3, "m2": ["ok"]})
    out = run_with_resilience(call, ["m1", "m2"], max_attempts=3, base_delay=0, sleep=_noop_sleep)
    assert out == "ok"
    assert calls == ["m1", "m1", "m1", "m2"]


def test_fatal_raises_without_fallback():
    call, calls = _scripted({"m1": [FakeAPIError(401)], "m2": ["ok"]})
    with pytest.raises(LLMConfigError):
        run_with_resilience(call, ["m1", "m2"], max_attempts=3, base_delay=0, sleep=_noop_sleep)
    assert calls == ["m1"]  # never reached the fallback


def test_all_models_fail_raises_unavailable():
    call, _ = _scripted({"m1": [FakeAPIError(503)] * 3, "m2": [FakeAPIError(429)]})
    with pytest.raises(LLMUnavailableError):
        run_with_resilience(call, ["m1", "m2"], max_attempts=3, base_delay=0, sleep=_noop_sleep)
