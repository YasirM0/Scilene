"""
AI Provider abstraction (#88).

An interface between Scilene and any language model, local or cloud --
services/recommender.py never depends on a specific LLM, and never
imports this module at all: it's used only by whatever AI-assisted UI
feature needs a suggestion, never by the deterministic search path.

    Research Idea / Abstract / Title
            │
            ▼
        AIProvider
            │
            ▼
      Structured JSON (AIResponse)
            │
            ▼
    (reviewed/edited by the user, then) Recommendation Engine

No concrete real provider is implemented here (#87 Online AI Provider,
future local model support) -- this is the interface only, matching
docs/AI_ARCHITECTURE.md's "Future-Proofing" section: one internal
interface so the underlying model can change later without changing
the UI. PlaceholderProvider below wraps the existing hardcoded
research_interpreter.py logic behind this same interface, so it's
demonstrably real and wireable, not just a decorative abstract class.
"""

from dataclasses import dataclass


@dataclass
class AIResponse:
    """
    Every AIProvider call returns this shape, regardless of provider
    or task -- see docs/AI_ARCHITECTURE.md's Reliability section.
    `ok` distinguishes "produced usable structured data" from "failed/
    timed out/invalid", so a caller never has to guess from an
    exception type what went wrong. A provider must never raise for an
    expected failure (timeout, invalid JSON, low confidence) -- only
    for a genuine programming error.
    """
    ok: bool
    data: dict | None = None
    confidence: float | None = None  # 0.0-1.0, when the provider can estimate one
    error: str | None = None  # human-readable, only set when ok=False


class AIProvider:
    """
    Parent class for every AI provider. A provider implements
    whichever tasks it supports; unimplemented ones raise
    NotImplementedError so a caller can check before assuming support.

    Every method takes and returns plain strings/dicts, never a
    provider-specific request/response object -- callers (and, per
    docs/AI_ARCHITECTURE.md, end users) should never need to know
    which provider answered.
    """

    name = ""

    def suggest_concepts(self, abstract):
        """Field of Study / Key Research Focus suggestions -- the task
        services/research_interpreter.py's placeholder stands in for
        today (docs/RESEARCH_INTERPRETER.md)."""
        raise NotImplementedError

    def detect_disciplines(self, abstract):
        """Research disciplines/concepts/topics (#102)."""
        raise NotImplementedError

    def generate_search_inputs(self, research_idea):
        """Idea -> suggested title/abstract/keywords (#85). No
        provider implements this yet -- generating prose needs a real
        model; unlike suggest_concepts(), a hardcoded placeholder
        wouldn't demonstrate real value, so #85 hasn't been built."""
        raise NotImplementedError


class PlaceholderProvider(AIProvider):
    """
    Wraps research_interpreter.py's hardcoded placeholder logic behind
    the real AIProvider interface -- proves the abstraction is usable
    end-to-end, not just decorative. A real provider implements the
    exact same interface; nothing else in the app would need to change
    to swap this one out for it.
    """

    name = "placeholder"

    def suggest_concepts(self, abstract):
        from services.research_interpreter import suggest_concepts

        if not abstract or not abstract.strip():
            return AIResponse(ok=False, error="No abstract provided.")

        return AIResponse(ok=True, data={"suggestions": suggest_concepts(abstract)}, confidence=None)
