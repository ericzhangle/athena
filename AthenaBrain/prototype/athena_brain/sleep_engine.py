from __future__ import annotations

from .abstraction_policy import AbstractionPolicy
from .attribute_normalizer import AttributeNormalizer
from .concept_graph import ConceptGraph
from .models import Experience, Perception, new_id, now_iso


class SleepEngine:
    """Consolidates experiences into candidate concepts and relations."""

    def __init__(self) -> None:
        self.normalizer = AttributeNormalizer()
        self.abstraction_policy = AbstractionPolicy()

    def consolidate(
        self,
        *,
        graph: ConceptGraph,
        experience: Experience,
        perception: Perception,
        source_concept: str,
        target_concept: str | None,
        relation_type: str | None,
        feature_evidence_refs: dict[tuple[str, str], str] | None = None,
        relation_evidence_id: str | None = None,
        evidence_statuses: dict[str, str] | None = None,
        evidence_sample_ids: dict[str, str] | None = None,
    ) -> dict[str, object]:
        operations: list[dict[str, object]] = []
        conflicts: list[dict[str, object]] = []
        concept = graph.get_or_create(source_concept)
        feature_evidence_refs = feature_evidence_refs or {}
        evidence_statuses = evidence_statuses or {}
        evidence_sample_ids = evidence_sample_ids or {}

        for feature in perception.features:
            differing_values = [
                attribute.value
                for attribute in concept.attributes
                if attribute.name == feature.category
                and not self.normalizer.same_or_compatible(
                    feature.category,
                    attribute.value,
                    feature.value,
                )
            ]
            if differing_values:
                normalized_new = self.normalizer.variation_values(feature.category, [feature.value])
                normalized_existing = self.normalizer.variation_values(feature.category, differing_values)
                conflicts.append(
                    {
                        "type": "attribute_variation",
                        "concept": source_concept,
                        "attribute": feature.category,
                        "existing_values": differing_values,
                        "new_value": feature.value,
                        "normalized_existing_values": normalized_existing,
                        "normalized_new_values": normalized_new,
                        "interpretation": "This may be a true variation rather than an error.",
                    }
                )

            graph.add_attribute(
                source_concept,
                attribute_name=feature.category,
                value=feature.value,
                confidence=min(0.8, feature.confidence * 0.75),
                evidence_refs=[
                    feature_evidence_refs.get(
                        (feature.category, feature.value),
                        self._feature_evidence_ref(
                            perception.perception_id,
                            feature.category,
                            perception.sample_id,
                        ),
                    )
                ],
            )

        operations.append(
            {
                "operation": "extract_candidate_attributes",
                "feature_count": len(perception.features),
                "source": perception.perception_id,
            }
        )

        if target_concept and relation_type:
            graph.add_relation(
                source_concept,
                relation_type=relation_type,
                target_name=target_concept,
                confidence=0.55,
                evidence_refs=[relation_evidence_id or experience.experience_id],
            )
            operations.append(
                {
                    "operation": "create_candidate_relation",
                    "relation": f"{source_concept} {relation_type} {target_concept}",
                    "confidence": 0.55,
                    "source": relation_evidence_id or experience.experience_id,
                }
            )

        questions = [
            {
                "question": f"{source_concept} 的这些观察特征是普遍特征，还是只属于这一个例子？",
                "reason": "single_example_cannot_support_generalization",
            }
        ]
        if target_concept:
            questions.append(
                {
                    "question": f"{target_concept} 的边界是什么？还有哪些东西属于 {target_concept}？",
                    "reason": "relation_target_concept_needs_definition",
                }
            )

        for question in questions:
            graph.add_open_question(source_concept, question["question"], question["reason"])

        for conflict in conflicts:
            graph.add_open_question(
                source_concept,
                f"{source_concept} 的 {conflict['attribute']} 是否允许多种表现？",
                "new_observation_differs_from_existing_attribute",
            )

        generalized_attributes = []
        for attribute_name, variations in graph.attribute_variations(source_concept).items():
            values = [attribute.value for attribute in variations]
            comparison_mode = self.normalizer.normalize(attribute_name, values[0])[
                "comparison_mode"
            ]
            if comparison_mode != "variation":
                graph.remove_generalized_attribute(source_concept, attribute_name)
                continue

            normalized_values = self.normalizer.variation_values(attribute_name, values)
            if len(normalized_values) < 2:
                graph.remove_generalized_attribute(source_concept, attribute_name)
                continue
            evidence_refs = []
            for attribute in variations:
                evidence_refs.extend(
                    ref
                    for ref in attribute.evidence_refs
                    if evidence_statuses.get(ref, "provisional") in {"provisional", "confirmed"}
                )
            unique_evidence_refs = sorted(set(evidence_refs))
            independent_sample_ids = self._independent_sample_ids(
                unique_evidence_refs,
                evidence_sample_ids,
            )
            confidence = min(0.75, 0.35 + 0.1 * len(set(normalized_values)))
            policy_result = self.abstraction_policy.classify(
                distinct_value_count=len(set(normalized_values)),
                evidence_count=len(unique_evidence_refs),
                independent_sample_count=len(independent_sample_ids),
                base_confidence=confidence,
            )
            graph.add_or_update_generalized_attribute(
                source_concept,
                attribute_name=attribute_name,
                values=normalized_values,
                confidence=float(policy_result["confidence"]),
                evidence_refs=unique_evidence_refs,
                generalization_status=str(policy_result["status"]),
            )
            generalized_attributes.append(
                {
                    "attribute": attribute_name,
                    "values": normalized_values,
                    "confidence": policy_result["confidence"],
                    "status": policy_result["status"],
                    "reason": policy_result["reason"],
                    "evidence_count": len(unique_evidence_refs),
                    "independent_sample_count": len(independent_sample_ids),
                    "interpretation": "Multiple observations suggest this may be a variable property of the concept.",
                }
            )

        parent_generalizations = graph.generalize_parent_concepts()

        report = {
            "sleep_report_id": new_id("sleep_report"),
            "timestamp": now_iso(),
            "mode": "prototype_consolidation",
            "input_refs": [experience.experience_id, perception.perception_id],
            "operations": operations,
            "conflicts_or_variations": conflicts,
            "generalized_attributes": generalized_attributes,
            "parent_generalizations": parent_generalizations,
            "generated_questions": questions,
            "summary": "Consolidated one experience into concept attributes and candidate relations.",
        }
        return report

    def _feature_evidence_ref(
        self,
        perception_id: str,
        category: str,
        sample_id: str | None,
    ) -> str:
        if sample_id:
            return f"{perception_id}:{category}:sample={sample_id}"
        return f"{perception_id}:{category}:sample=unknown"

    def _independent_sample_ids(
        self,
        evidence_refs: list[str],
        evidence_sample_ids: dict[str, str],
    ) -> set[str]:
        sample_ids = set()
        for ref in evidence_refs:
            if ref in evidence_sample_ids:
                sample_ids.add(evidence_sample_ids[ref])
                continue
            if "sample=" not in ref:
                sample_ids.add(ref)
                continue
            sample_ids.add(ref.split("sample=", 1)[1])
        return sample_ids
