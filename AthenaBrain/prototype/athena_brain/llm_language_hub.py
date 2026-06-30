from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, request


class LocalLLMUnavailableError(RuntimeError):
    pass


@dataclass
class LocalLLMConfig:
    backend: str = "ollama"
    endpoint: str = "http://127.0.0.1:11434/api/chat"
    model: str = ""
    timeout_seconds: int = 180
    keep_alive: str = "30m"
    think: bool = False


class LocalLanguageHub:
    """Local-model language hub for grounded ingestion and answering.

    The model is only allowed to:
    1. Convert text into structured candidates.
    2. Convert grounded Athena memory bundles into answer language.
    """

    def __init__(self, config: LocalLLMConfig | None = None) -> None:
        self.config = config or LocalLLMConfig(
            backend=os.getenv("ATHENA_LOCAL_LLM_BACKEND", "ollama"),
            endpoint=os.getenv("ATHENA_LOCAL_LLM_ENDPOINT", "http://127.0.0.1:11434/api/chat"),
            model=os.getenv("ATHENA_LOCAL_LLM_MODEL", ""),
            timeout_seconds=int(os.getenv("ATHENA_LOCAL_LLM_TIMEOUT", "180")),
            keep_alive=os.getenv("ATHENA_LOCAL_LLM_KEEP_ALIVE", "30m"),
            think=os.getenv("ATHENA_LOCAL_LLM_THINK", "false").strip().lower() == "true",
        )
        if not self.config.model.strip():
            self.config.model = self._discover_default_model()

    def is_available(self) -> bool:
        return bool(self.config.model.strip())

    def unavailable_reason(self) -> str:
        if self.is_available():
            return ""
        return "ATHENA_LOCAL_LLM_MODEL is not configured."

    def parse_knowledge_text(self, *, text: str, known_concepts: list[str]) -> dict[str, Any]:
        self._require_available()
        system_prompt = (
            "You are Athena's language ingestion hub. "
            "Your job is to read a short text and return only strict JSON. "
            "Do not answer conversationally. "
            "Do not invent facts beyond the text. "
            "Return candidate concepts, relations, attributes, uncertainties, and suggested questions. "
            "Use relation types from this set when possible: "
            "is-a, is-not-a, contains, supports, made-of, related-to, can_affect, may_trigger. "
            "Use canonical concept names in concise TitleCase when possible."
        )
        user_prompt = json.dumps(
            {
                "task": "parse_knowledge_text",
                "text": text,
                "known_concepts": known_concepts,
                "output_schema": {
                    "concepts": [{"name": "ConceptName", "surface": "surface form in text"}],
                    "relations": [
                        {
                            "subject": "ConceptName",
                            "relation_type": "is-a",
                            "target": "ConceptName",
                            "statement": "Original supporting statement",
                        }
                    ],
                    "attributes": [
                        {
                            "subject": "ConceptName",
                            "attribute_name": "edibility",
                            "attribute_value": "Short grounded value",
                            "statement": "Original supporting statement",
                        }
                    ],
                    "suggested_questions": [
                        {
                            "concept": "ConceptName",
                            "question": "Natural language curiosity question",
                            "reason": "short_reason",
                        }
                    ],
                    "uncertainties": ["list uncertain points from the text"],
                },
            },
            ensure_ascii=False,
        )
        return self._chat_json(system_prompt=system_prompt, user_prompt=user_prompt)

    def compose_grounded_answer(self, *, question: str, grounded_bundle: dict[str, Any]) -> dict[str, Any]:
        self._require_available()
        system_prompt = (
            "You are Athena's grounded answer composer. "
            "You must answer only from the provided grounded memory bundle. "
            "Do not use outside knowledge. "
            "If the bundle does not support an answer, say you do not know yet. "
            "Return only strict JSON."
        )
        user_prompt = json.dumps(
            {
                "task": "compose_grounded_answer",
                "question": question,
                "grounded_bundle": grounded_bundle,
                "output_schema": {
                    "answer": "Grounded natural language answer",
                    "used_concepts": ["ConceptName"],
                    "used_relations": [["ConceptA", "relation", "ConceptB"]],
                    "used_event_ids": ["event_xxx"],
                    "used_evidence_ids": ["evidence_xxx"],
                    "confidence": 0.0,
                    "insufficient_memory": False,
                },
            },
            ensure_ascii=False,
        )
        return self._chat_json(system_prompt=system_prompt, user_prompt=user_prompt)

    def _require_available(self) -> None:
        if not self.is_available():
            raise LocalLLMUnavailableError(self.unavailable_reason())

    def _discover_default_model(self) -> str:
        if self.config.backend != "ollama":
            return ""
        tags_url = self.config.endpoint.removesuffix("/api/chat") + "/api/tags"
        req = request.Request(tags_url, method="GET")
        try:
            with request.urlopen(req, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (error.URLError, ValueError, KeyError, TypeError):
            return ""

        models = [
            str(item.get("name", "")).strip()
            for item in payload.get("models", [])
            if str(item.get("name", "")).strip()
        ]
        if "qwen3:8b" in models:
            return "qwen3:8b"
        if models:
            return models[0]
        return ""

    def _chat_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if self.config.backend != "ollama":
            raise LocalLLMUnavailableError(
                f"Unsupported local LLM backend: {self.config.backend}. "
                "Only ollama-style local HTTP backend is implemented right now."
            )
        payload = {
            "model": self.config.model,
            "stream": False,
            "format": "json",
            "keep_alive": self.config.keep_alive,
            "think": self.config.think,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        request_body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.config.endpoint,
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except error.URLError as exc:
            raise LocalLLMUnavailableError(
                f"Failed to reach local LLM endpoint {self.config.endpoint}: {exc}"
            ) from exc

        try:
            envelope = json.loads(raw)
            content = envelope["message"]["content"]
            return json.loads(content)
        except (KeyError, TypeError, ValueError) as exc:
            raise LocalLLMUnavailableError(
                "Local LLM response was not valid JSON in the expected Ollama chat format."
            ) from exc


class FixedLocalLanguageHub(LocalLanguageHub):
    """Deterministic test double for validation scripts."""

    def __init__(
        self,
        *,
        parsed_responses: dict[str, dict[str, Any]] | None = None,
        answer_responses: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(LocalLLMConfig(model="fixed-test-hub"))
        self.parsed_responses = parsed_responses or {}
        self.answer_responses = answer_responses or {}

    def parse_knowledge_text(self, *, text: str, known_concepts: list[str]) -> dict[str, Any]:
        if text in self.parsed_responses:
            return self.parsed_responses[text]
        raise LocalLLMUnavailableError(f"No fixed parse response configured for: {text}")

    def compose_grounded_answer(self, *, question: str, grounded_bundle: dict[str, Any]) -> dict[str, Any]:
        if question in self.answer_responses:
            return self.answer_responses[question]
        raise LocalLLMUnavailableError(f"No fixed grounded answer configured for: {question}")
