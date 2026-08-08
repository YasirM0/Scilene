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

Two concrete providers exist here: PlaceholderProvider (wraps the
existing hardcoded research_interpreter.py logic) and CloudAIProvider
(#87 -- a real, generic HTTP client for any cloud AI service that
speaks the request/response contract below; not wired to a specific
paid vendor, since this project has no API key or budget to commit to
one, but genuinely functional against anything implementing the
contract -- see its class docstring, and docs/AI_ARCHITECTURE.md's
"Future-Proofing" section for the contract itself). Local model
support (also future work per docs/AI_ARCHITECTURE.md) would be a
third provider implementing the exact same contract -- that's the
point: services/recommender.py never depends on a specific LLM, and
never imports this module at all, and neither does any caller need to
know or care which provider answered.
"""

from dataclasses import dataclass

import requests


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


class CloudAIProvider(AIProvider):
    """
    Cloud-based AI for users who don't (or can't) install a local
    model (#87). Genuinely functional -- not a stub -- against any
    endpoint implementing this request/response contract, but not
    wired to a specific paid vendor: this project has no API key or
    hosting budget to commit to one, and hardcoding a "real" call to a
    service nobody's actually running would just be a different kind
    of fake AI. Verified in tests/test_ai_provider.py against a real
    local HTTP server implementing the contract, both success and
    failure paths.

    Request/response contract (docs/AI_ARCHITECTURE.md's "Future-
    Proofing" section -- this is intentionally the SAME contract any
    future local-model provider should speak too, which is what makes
    "local and cloud AI interchangeable" concretely true rather than
    aspirational):

        POST {endpoint_url}
        {"task": "suggest_concepts" | "detect_disciplines" | "generate_search_inputs",
         "input": {...task-specific fields...}}

        -> 200 OK
        {"ok": true, "data": {...}, "confidence": 0.0-1.0 | null, "error": null}

    A malformed response, a non-200 status, a timeout, or a connection
    failure all produce AIResponse(ok=False, error=...) -- per
    AIProvider's contract, a provider never raises for an expected
    failure, only for a genuine programming error (e.g. constructing
    this class with no endpoint_url).
    """

    name = "cloud"

    def __init__(self, endpoint_url, api_key=None, timeout=10):
        if not endpoint_url:
            raise ValueError("CloudAIProvider requires an endpoint_url.")
        self.endpoint_url = endpoint_url
        self.api_key = api_key
        self.timeout = timeout

    def _call(self, task, input_payload):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = requests.post(
                self.endpoint_url,
                json={"task": task, "input": input_payload},
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            return AIResponse(ok=False, error=f"Request failed: {exc}")

        if response.status_code != 200:
            return AIResponse(ok=False, error=f"Provider returned HTTP {response.status_code}")

        try:
            body = response.json()
        except ValueError:
            return AIResponse(ok=False, error="Provider response was not valid JSON.")

        if not isinstance(body, dict) or "ok" not in body:
            return AIResponse(ok=False, error="Provider response did not match the expected contract.")

        return AIResponse(
            ok=bool(body.get("ok")),
            data=body.get("data"),
            confidence=body.get("confidence"),
            error=body.get("error"),
        )

    def suggest_concepts(self, abstract):
        if not abstract or not abstract.strip():
            return AIResponse(ok=False, error="No abstract provided.")
        return self._call("suggest_concepts", {"abstract": abstract})

    def detect_disciplines(self, abstract):
        if not abstract or not abstract.strip():
            return AIResponse(ok=False, error="No abstract provided.")
        return self._call("detect_disciplines", {"abstract": abstract})

    def generate_search_inputs(self, research_idea):
        if not research_idea or not research_idea.strip():
            return AIResponse(ok=False, error="No research idea provided.")
        return self._call("generate_search_inputs", {"research_idea": research_idea})
