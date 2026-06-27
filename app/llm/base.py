"""Provider-agnostic LLM interface.

Deliberately tiny: text in, text out. Anything provider-specific (JSON mode,
tools, safety settings) stays inside the concrete provider so /ask never depends
on which LLM is behind it — swapping providers is a one-line factory change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Return the model's text response to `user`, guided by `system`."""
        ...
