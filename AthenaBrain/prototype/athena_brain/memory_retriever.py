from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .concept_graph import ConceptGraph
from .evidence_ledger import EvidenceLedger
from .memory_index import MemoryIndex
from .store import JsonMemoryStore


class MemoryRetriever:
    """Builds grounded memory bundles for question answering."""

    def retrieve_neighborhood(
        self,
        *,
        anchor_names: list[str],
        memory_index: MemoryIndex,
        hops: int = 1,
    ) -> dict[str, Any]:
        return memory_index.recall_neighborhood(
            anchor_names=anchor_names,
            hops=hops,
        )

    def retrieve(
        self,
        *,
        question: str,
        graph: ConceptGraph,
        store: JsonMemoryStore,
        evidence_ledger: EvidenceLedger,
    ) -> dict[str, Any]:
        matched_concepts = self._matched_concepts(question, graph)
        concept_names = [concept["name"] for concept in matched_concepts]
        relation_rows = self._relation_rows(graph, concept_names)
        examples = self._examples_for(graph, concept_names)
        question_type = self._question_type(question)
        requested_attribute = self._requested_attribute(question)
        event_rows = self._matched_events(store, concept_names)
        evidence_rows = self._matched_evidence(evidence_ledger, concept_names)
        return {
            "question": question,
            "question_type": question_type,
            "requested_attribute": requested_attribute,
            "matched_concepts": concept_names,
            "concepts": matched_concepts,
            "relations": relation_rows,
            "examples": examples,
            "events": event_rows,
            "evidence": evidence_rows,
            "unknown": not (concept_names or relation_rows or event_rows or evidence_rows),
        }

    def _matched_concepts(self, question: str, graph: ConceptGraph) -> list[dict[str, Any]]:
        normalized_question = question.casefold()
        matches = []
        for concept in sorted(graph.all_concepts(), key=lambda item: len(item.name), reverse=True):
            if concept.name.casefold() not in normalized_question:
                continue
            matches.append(
                {
                    "name": concept.name,
                    "maturity": concept.maturity,
                    "description": concept.description,
                    "attributes": [
                        {
                            "name": attribute.name,
                            "value": attribute.value,
                            "scope": attribute.scope,
                            "confidence": attribute.confidence,
                        }
                        for attribute in concept.attributes
                    ],
                    "relations": [
                        {
                            "relation_type": relation.relation_type,
                            "target": relation.target_concept,
                            "confidence": relation.confidence,
                        }
                        for relation in concept.relations
                    ],
                }
            )
        return matches

    def _relation_rows(self, graph: ConceptGraph, concept_names: list[str]) -> list[list[str]]:
        if not concept_names:
            return []
        rows: list[list[str]] = []
        concept_name_set = set(concept_names)
        for concept in graph.all_concepts():
            if concept.name not in concept_name_set:
                continue
            for relation in concept.relations:
                if relation.target_concept in concept_name_set or concept.name in concept_name_set:
                    rows.append([concept.name, relation.relation_type, relation.target_concept])
        return rows

    def _examples_for(self, graph: ConceptGraph, concept_names: list[str]) -> dict[str, list[str]]:
        examples: dict[str, list[str]] = {}
        for name in concept_names:
            concept = graph.get_or_create(name)
            if concept.examples:
                examples[name] = [str(item.get("concept")) for item in concept.examples]
        return examples

    def _matched_events(self, store: JsonMemoryStore, concept_names: list[str]) -> list[dict[str, Any]]:
        if not concept_names:
            return []
        concept_name_set = set(concept_names)
        matched = []
        for path in store.list_records("events"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            joined = json.dumps(payload, ensure_ascii=False)
            if concept_name_set and not any(name in joined for name in concept_name_set):
                continue
            matched.append(
                {
                    "event_id": payload.get("event_id", Path(path).stem),
                    "event_type": payload.get("event_type"),
                    "summary": payload.get("summary"),
                }
            )
        return matched[:12]

    def _matched_evidence(self, evidence_ledger: EvidenceLedger, concept_names: list[str]) -> list[dict[str, Any]]:
        if not concept_names:
            return []
        concept_name_set = set(concept_names)
        matched = []
        for evidence in evidence_ledger.evidence.values():
            if not evidence_ledger.is_active(evidence.evidence_id):
                continue
            joined = " ".join(
                str(value)
                for value in [
                    evidence.claim.subject,
                    evidence.claim.predicate,
                    evidence.claim.object,
                    evidence.claim.statement,
                ]
                if value
            )
            if concept_name_set and not any(name in joined for name in concept_name_set):
                continue
            matched.append(
                {
                    "evidence_id": evidence.evidence_id,
                    "subject": evidence.claim.subject,
                    "predicate": evidence.claim.predicate,
                    "object": evidence.claim.object,
                    "statement": evidence.claim.statement,
                    "status": evidence.status,
                    "confidence": evidence.confidence,
                }
            )
        return matched[:20]

    def _question_type(self, question: str) -> str:
        lowered = question.casefold()
        if "describe" in lowered or "描述" in question or "知道什么" in question or "what do you know" in lowered:
            return "describe"
        if "belongs to" in lowered or "属于什么" in question:
            return "belongs_to"
        if "examples" in lowered or "哪些例子" in question:
            return "examples_of"
        if re.search(r"\bis\s+.+\s+a[n]?\s+", lowered) or "是不是一种" in question:
            return "is_a"
        if "why did" in lowered or "为什么会问" in question:
            return "why_asked"
        return "open_question"

    def _requested_attribute(self, question: str) -> str | None:
        lowered = question.casefold()
        if "color" in lowered or "颜色" in question:
            return "color"
        if "shape" in lowered or "形状" in question:
            return "shape"
        if "edible" in lowered or "能吃" in question or "可以吃" in question:
            return "edibility"
        return None
