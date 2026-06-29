from __future__ import annotations

from .concept_graph import ConceptGraph
from .models import Concept


class SimilarityEngine:
    """Finds candidate classifications from shared observed features.

    Similarity does not create facts. It only produces hypotheses/questions such
    as "Grape shares traits with known Fruit examples; is it also Fruit?".
    """

    def candidate_parent_questions(
        self,
        graph: ConceptGraph,
        concept: Concept,
        *,
        limit: int = 2,
    ) -> list[dict[str, object]]:
        if self._has_parent(concept):
            return []

        concept_features = self.features_for(concept)
        if not concept_features:
            return []

        candidates = []
        for parent in graph.all_concepts():
            if parent.name == concept.name:
                continue
            if self._has_negative_relation(concept, parent.name):
                continue
            if self._is_child_of(graph, child_name=parent.name, parent_name=concept.name):
                continue
            if not parent.examples:
                continue
            example_features = self._example_features(graph, parent)
            if not example_features:
                continue
            shared = sorted(concept_features & example_features)
            score = len(shared) / max(1, min(len(concept_features), len(example_features)))
            if score < 0.25:
                continue
            candidates.append(
                {
                    "parent": parent.name,
                    "score": round(score, 3),
                    "shared_features": shared[:6],
                    "example_count": len(parent.examples),
                }
            )

        return sorted(candidates, key=lambda item: (-float(item["score"]), str(item["parent"])))[:limit]

    def features_for(self, concept: Concept) -> set[str]:
        features = set()
        for attribute in concept.attributes:
            if attribute.scope == "inferred":
                continue
            lowered_value = attribute.value.lower()
            if attribute.name not in {"edibility", "use"}:
                features.add(f"attr:{attribute.name}")
            if any(marker in lowered_value for marker in ["cannot be eaten", "not edible", "not food"]):
                features.add("value:not_edible")
                continue
            if any(marker in lowered_value for marker in ["can be eaten", "directly eaten", "usually edible"]):
                features.add("value:edible")
            for marker in [
                "sweet",
                "vitamin",
                "fiber",
                "water",
                "plant",
            ]:
                if marker in lowered_value:
                    features.add(f"value:{marker}")
        for relation in concept.relations:
            if relation.relation_type in {"is-a", "is-not-a"}:
                continue
            features.add(f"rel:{relation.relation_type}")
            features.add(f"rel:{relation.relation_type}:{relation.target_concept}")
        return features

    def _example_features(self, graph: ConceptGraph, parent: Concept) -> set[str]:
        features = set()
        for example in parent.examples:
            child = graph.get_or_create(str(example["concept"]))
            features.update(self.features_for(child))
        return features

    def _has_parent(self, concept: Concept) -> bool:
        return any(relation.relation_type == "is-a" for relation in concept.relations)

    def _has_negative_relation(self, concept: Concept, parent_name: str) -> bool:
        return any(
            relation.relation_type == "is-not-a"
            and relation.target_concept == parent_name
            for relation in concept.relations
        )

    def _is_child_of(self, graph: ConceptGraph, *, child_name: str, parent_name: str) -> bool:
        child = graph.get_or_create(child_name)
        return any(
            relation.relation_type == "is-a"
            and relation.target_concept == parent_name
            for relation in child.relations
        )
