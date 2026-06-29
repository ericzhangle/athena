from __future__ import annotations

import re

from .concept_graph import ConceptGraph
from .models import Rule


class ReasoningEngine:
    """Applies small traceable rules over the concept graph.

    This is not a general logic engine yet. It supports the first useful
    cognitive step: generalizing an answer about a parent concept with an
    exception, then using that rule to reduce repeated curiosity questions.
    """

    def extract_rules_from_answer(
        self,
        *,
        answer: str,
        source_evidence_id: str,
    ) -> list[Rule]:
        text = answer.strip()
        lowered = text.lower()
        rules = []

        match = re.search(
            r"\b(?P<subject>[A-Za-z][A-Za-z0-9 _-]*?)\s+"
            r"(?:is|are)\s+(?:usually|generally|often|mostly)\s+"
            r"(?P<property>edible|able\s+to\s+be\s+eaten|safe\s+to\s+eat)",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            subject = self._canonicalize(match.group("subject"))
            exceptions = self._extract_exceptions(text)
            rules.append(
                Rule(
                    rule_type="default_property_with_exception",
                    subject_concept=subject,
                    predicate="edibility",
                    object_value="usually_edible",
                    condition={"relation": "is-a", "target": subject},
                    exceptions=exceptions,
                    source_evidence_id=source_evidence_id,
                    confidence=0.58,
                )
            )
            return rules

        mentions_edible = "吃" in answer or "edible" in lowered or "eat" in lowered
        has_general_signal = any(marker in answer for marker in ["一般", "通常", "大多", "都能"])
        if mentions_edible and has_general_signal:
            subject = self._first_known_subject_candidate(answer)
            if subject:
                rules.append(
                    Rule(
                        rule_type="default_property_with_exception",
                        subject_concept=subject,
                        predicate="edibility",
                        object_value="usually_edible",
                        condition={"relation": "is-a", "target": subject},
                        exceptions=self._extract_exceptions(answer),
                        source_evidence_id=source_evidence_id,
                        confidence=0.54,
                    )
                )
        return rules

    def apply_rules(self, graph: ConceptGraph, rules: list[Rule]) -> list[dict[str, object]]:
        inferences: list[dict[str, object]] = []
        for rule in rules:
            if rule.status != "provisional":
                continue
            if not self._is_default_edibility_rule(rule):
                continue
            inferences.extend(self._apply_default_edibility_rule(graph, rule))
        return inferences

    def _apply_default_edibility_rule(
        self,
        graph: ConceptGraph,
        rule: Rule,
    ) -> list[dict[str, object]]:
        inferences = []
        for concept in graph.all_concepts():
            if not self._is_child_of(concept, rule.subject_concept):
                continue
            if self._matches_exception(concept.name, rule.exceptions):
                continue

            value = (
                f"Inferred from rule {rule.rule_id}: {concept.name} is a {rule.subject_concept}, "
                f"and {rule.subject_concept} is usually edible unless it matches "
                f"{', '.join(rule.exceptions) or 'an exception'}."
            )
            graph.add_attribute(
                concept.name,
                attribute_name="edibility",
                value=value,
                confidence=min(0.72, rule.confidence * 0.85),
                evidence_refs=[rule.rule_id],
                scope="inferred",
                generalization_status="inferred_from_rule",
            )
            closed_count = graph.answer_questions_by_inference(
                concept.name,
                keyword="eat",
                inference_ref=rule.rule_id,
                answer=f"Inferred from a default rule: {concept.name} is usually edible, with possible exceptions.",
            )
            closed_count += graph.answer_questions_by_inference(
                concept.name,
                keyword="吃",
                inference_ref=rule.rule_id,
                answer=f"根据默认规则推断：{concept.name} 通常可以吃，但仍要注意例外。",
            )
            inferences.append(
                {
                    "rule_id": rule.rule_id,
                    "concept": concept.name,
                    "attribute": "edibility",
                    "value": "usually_edible",
                    "closed_question_count": closed_count,
                    "confidence": min(0.72, rule.confidence * 0.85),
                }
            )
        return inferences

    def _is_default_edibility_rule(self, rule: Rule) -> bool:
        return (
            rule.rule_type == "default_property_with_exception"
            and rule.predicate == "edibility"
            and rule.object_value == "usually_edible"
        )

    def _is_child_of(self, concept, parent_name: str) -> bool:
        return any(
            relation.relation_type == "is-a"
            and relation.target_concept == parent_name
            for relation in concept.relations
        )

    def _matches_exception(self, concept_name: str, exceptions: list[str]) -> bool:
        lowered = concept_name.lower()
        return any(exception.lower() in lowered for exception in exceptions)

    def _extract_exceptions(self, text: str) -> list[str]:
        match = re.search(r"\b(?:except|unless)\s+(.+?)(?:[。.!?]|$)", text, flags=re.IGNORECASE)
        if not match:
            return []
        raw_items = re.split(r",|\band\b|\bor\b", match.group(1))
        return [
            self._canonicalize(item)
            for item in raw_items
            if self._canonicalize(item)
        ]

    def _first_known_subject_candidate(self, text: str) -> str | None:
        match = re.search(r"([A-Za-z][A-Za-z0-9 _-]+|[\u4e00-\u9fff]+)", text)
        if not match:
            return None
        return self._canonicalize(match.group(1))

    def _canonicalize(self, value: str) -> str:
        cleaned = re.sub(r"\b(the|a|an|some|most|many|usually|generally)\b", " ", value, flags=re.IGNORECASE)
        cleaned = " ".join(cleaned.strip(" ,.;:!?。！？").split())
        if not cleaned:
            return ""
        if re.search(r"[\u4e00-\u9fff]", cleaned):
            aliases = {
                "水果": "Fruit",
                "塑料": "Plastic",
                "塑料水果": "PlasticFruit",
            }
            return aliases.get(cleaned, cleaned)
        words = re.split(r"[\s_\-]+", cleaned)
        return "".join(word[:1].upper() + word[1:] for word in words if word)
