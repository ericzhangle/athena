from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Concept, concept_from_dict
from .store import JsonMemoryStore


@dataclass
class ConceptRecord:
    concept_id: str
    name: str
    maturity: str
    confidence: float
    description: str
    neighbors: set[str]
    evidence_refs: set[str]


class MemoryIndex:
    """Lightweight disk-backed index for local concept recall."""

    ALIASES = {
        "苹果": "Apple",
        "葡萄": "Grape",
        "梨": "Pear",
        "桃子": "Peach",
        "香蕉": "Banana",
        "番茄": "Tomato",
        "水果": "Fruit",
        "食物": "Food",
        "食品": "Food",
        "车辆": "Vehicle",
        "汽车": "Car",
    }

    def __init__(self, store: JsonMemoryStore) -> None:
        self.store = store
        self._records_by_id: dict[str, ConceptRecord] = {}
        self._ids_by_key: dict[str, set[str]] = {}
        self.refresh()

    def refresh(self) -> None:
        records_by_id: dict[str, ConceptRecord] = {}
        ids_by_key: dict[str, set[str]] = {}
        raw_payloads: dict[str, dict[str, Any]] = {}

        for path in self.store.list_records("concepts"):
            try:
                payload = self.store.load("concepts", path.stem)
            except (OSError, KeyError, ValueError, TypeError):
                continue
            concept_id = str(payload.get("concept_id", path.stem))
            raw_payloads[concept_id] = payload
            name = str(payload.get("name", "")).strip()
            if not name:
                continue
            key = self._key(name)
            ids_by_key.setdefault(key, set()).add(concept_id)

        for concept_id, payload in raw_payloads.items():
            name = str(payload.get("name", "")).strip()
            if not name:
                continue
            neighbors = set()
            evidence_refs = set(str(ref) for ref in payload.get("evidence_refs", []))

            for relation in payload.get("relations", []):
                target_name = str(relation.get("target_concept", "")).strip()
                if target_name:
                    neighbors.add(target_name)
                for ref in relation.get("evidence_refs", []):
                    evidence_refs.add(str(ref))

            for item in payload.get("examples", []):
                child_name = str(item.get("concept", "")).strip()
                if child_name:
                    neighbors.add(child_name)
                child_id = str(item.get("concept_id", "")).strip()
                if child_id and child_id in raw_payloads:
                    child_name = str(raw_payloads[child_id].get("name", "")).strip()
                    if child_name:
                        neighbors.add(child_name)

            for item in payload.get("counterexamples", []):
                child_name = str(item.get("concept", "")).strip()
                if child_name:
                    neighbors.add(child_name)

            for attribute in payload.get("attributes", []):
                for ref in attribute.get("evidence_refs", []):
                    evidence_refs.add(str(ref))

            records_by_id[concept_id] = ConceptRecord(
                concept_id=concept_id,
                name=name,
                maturity=str(payload.get("maturity", "seed")),
                confidence=float(payload.get("confidence", 0.1)),
                description=str(payload.get("description", "")),
                neighbors=neighbors,
                evidence_refs=evidence_refs,
            )

        for record in records_by_id.values():
            for neighbor_name in list(record.neighbors):
                neighbor_ids = ids_by_key.get(self._key(neighbor_name), set())
                for neighbor_id in neighbor_ids:
                    neighbor_record = records_by_id.get(neighbor_id)
                    if neighbor_record is not None:
                        neighbor_record.neighbors.add(record.name)

        self._records_by_id = records_by_id
        self._ids_by_key = ids_by_key

    def list_concept_records(self) -> list[ConceptRecord]:
        return sorted(self._records_by_id.values(), key=lambda item: item.name)

    def concept_names_in_text(self, text: str) -> list[str]:
        lowered = text.casefold()
        matches = []
        seen = set()
        candidate_names = sorted(
            {record.name for record in self._records_by_id.values()},
            key=len,
            reverse=True,
        )
        for name in candidate_names:
            if name.casefold() in lowered and name not in seen:
                matches.append(name)
                seen.add(name)
        for alias, canonical in self.ALIASES.items():
            if alias in text and canonical not in seen and self.resolve_concept_ids([canonical]):
                matches.append(canonical)
                seen.add(canonical)
        return matches

    def resolve_concept_ids(self, names: list[str]) -> list[str]:
        concept_ids = []
        seen = set()
        for name in names:
            normalized = self.ALIASES.get(name.strip(), name.strip())
            key = self._key(normalized)
            for concept_id in sorted(self._ids_by_key.get(key, set())):
                if concept_id in seen:
                    continue
                concept_ids.append(concept_id)
                seen.add(concept_id)
        return concept_ids

    def load_concepts_by_ids(self, concept_ids: list[str]) -> list[Concept]:
        concepts = []
        seen = set()
        for concept_id in concept_ids:
            if concept_id in seen:
                continue
            seen.add(concept_id)
            try:
                payload = self.store.load("concepts", concept_id)
            except (OSError, KeyError, ValueError, TypeError):
                continue
            concepts.append(concept_from_dict(payload))
        return concepts

    def recall_neighborhood(
        self,
        *,
        anchor_names: list[str],
        hops: int = 1,
    ) -> dict[str, Any]:
        anchor_ids = self.resolve_concept_ids(anchor_names)
        if not anchor_ids:
            return {
                "anchor_names": anchor_names,
                "anchor_ids": [],
                "concept_ids": [],
                "concepts": [],
                "evidence_ids": [],
            }

        visited = set(anchor_ids)
        frontier = set(anchor_ids)
        for _ in range(max(0, hops)):
            next_frontier = set()
            for concept_id in frontier:
                record = self._records_by_id.get(concept_id)
                if record is None:
                    continue
                for neighbor_name in record.neighbors:
                    for neighbor_id in self._ids_by_key.get(self._key(neighbor_name), set()):
                        if neighbor_id in visited:
                            continue
                        visited.add(neighbor_id)
                        next_frontier.add(neighbor_id)
            frontier = next_frontier
            if not frontier:
                break

        concepts = self.load_concepts_by_ids(sorted(visited))
        evidence_ids = sorted(
            {
                evidence_id
                for concept in concepts
                for evidence_id in self._evidence_refs_for_concept(concept)
            }
        )
        return {
            "anchor_names": anchor_names,
            "anchor_ids": anchor_ids,
            "concept_ids": sorted(visited),
            "concepts": concepts,
            "evidence_ids": evidence_ids,
        }

    def load_concept_by_name(self, name: str) -> Concept | None:
        concept_ids = self.resolve_concept_ids([name])
        concepts = self.load_concepts_by_ids(concept_ids[:1])
        return concepts[0] if concepts else None

    def _evidence_refs_for_concept(self, concept: Concept) -> set[str]:
        refs = set(concept.evidence_refs)
        for relation in concept.relations:
            refs.update(relation.evidence_refs)
        for attribute in concept.attributes:
            refs.update(attribute.evidence_refs)
        return refs

    @staticmethod
    def _key(name: str) -> str:
        return name.strip().lower()
