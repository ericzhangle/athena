from __future__ import annotations

from .models import Concept, ConceptAttribute, Relation


class ConceptGraph:
    """In-memory concept graph for the first BabyBrain prototype."""

    ANSWERED_QUESTION_STATUSES = {
        "answered",
        "answered_by_inference",
        "answered_by_reference",
        "answered_by_relation",
        "answered_by_inverse_relation",
        "rejected_by_relation",
    }

    def __init__(self) -> None:
        self.concepts: dict[str, Concept] = {}

    def load(self, concepts: list[Concept]) -> None:
        for concept in concepts:
            self._dedupe_concept(concept)
            key = self._key(concept.name)
            existing = self.concepts.get(key)
            if existing is None or concept.updated_at >= existing.updated_at:
                self.concepts[key] = concept

    def get_or_create(self, name: str, *, display_name: str | None = None) -> Concept:
        key = self._key(name)
        if key not in self.concepts:
            self.concepts[key] = Concept(
                name=name,
                display_name=display_name,
                description=f"Early concept candidate for {display_name or name}.",
            )
        return self.concepts[key]

    def add_attribute(
        self,
        concept_name: str,
        *,
        attribute_name: str,
        value: str,
        confidence: float,
        evidence_refs: list[str],
        scope: str = "observed_example",
        generalization_status: str = "not_yet_general",
    ) -> Concept:
        concept = self.get_or_create(concept_name)
        for existing in concept.attributes:
            if existing.name == attribute_name and existing.value == value:
                existing.confidence = min(0.95, max(existing.confidence, confidence))
                existing.scope = scope if existing.scope == "observed_example" else existing.scope
                existing.generalization_status = (
                    generalization_status
                    if existing.generalization_status == "not_yet_general"
                    else existing.generalization_status
                )
                for ref in evidence_refs:
                    if ref not in existing.evidence_refs:
                        existing.evidence_refs.append(ref)
                concept.evidence_refs.extend(ref for ref in evidence_refs if ref not in concept.evidence_refs)
                concept.confidence = min(0.95, max(concept.confidence, confidence * 0.75))
                concept.touch()
                return concept

        concept.attributes.append(
            ConceptAttribute(
                name=attribute_name,
                value=value,
                confidence=confidence,
                evidence_refs=evidence_refs,
                scope=scope,
                generalization_status=generalization_status,
            )
        )
        concept.evidence_refs.extend(ref for ref in evidence_refs if ref not in concept.evidence_refs)
        concept.confidence = min(0.95, max(concept.confidence, confidence * 0.75))
        concept.maturity = "early" if concept.confidence >= 0.35 else concept.maturity
        concept.touch()
        return concept

    def add_or_update_generalized_attribute(
        self,
        concept_name: str,
        *,
        attribute_name: str,
        values: list[str],
        confidence: float,
        evidence_refs: list[str],
        generalization_status: str = "generalized_candidate",
    ) -> Concept:
        concept = self.get_or_create(concept_name)
        generalized_name = f"{attribute_name}_variation"
        normalized_values = sorted(set(values))
        value = f"{attribute_name} can vary: " + " / ".join(normalized_values)

        for existing in concept.attributes:
            if existing.name == generalized_name:
                existing.value = value
                existing.confidence = min(0.95, max(existing.confidence, confidence))
                existing.scope = "concept_level"
                existing.generalization_status = generalization_status
                for ref in evidence_refs:
                    if ref not in existing.evidence_refs:
                        existing.evidence_refs.append(ref)
                concept.evidence_refs.extend(ref for ref in evidence_refs if ref not in concept.evidence_refs)
                concept.confidence = min(0.95, max(concept.confidence, confidence * 0.9))
                concept.touch()
                return concept

        concept.attributes.append(
            ConceptAttribute(
                name=generalized_name,
                value=value,
                confidence=confidence,
                evidence_refs=evidence_refs,
                scope="concept_level",
                generalization_status=generalization_status,
            )
        )
        concept.evidence_refs.extend(ref for ref in evidence_refs if ref not in concept.evidence_refs)
        concept.confidence = min(0.95, max(concept.confidence, confidence * 0.9))
        concept.touch()
        return concept

    def remove_generalized_attribute(self, concept_name: str, attribute_name: str) -> None:
        concept = self.get_or_create(concept_name)
        generalized_name = f"{attribute_name}_variation"
        original_len = len(concept.attributes)
        concept.attributes = [
            attribute for attribute in concept.attributes if attribute.name != generalized_name
        ]
        if len(concept.attributes) != original_len:
            concept.touch()

    def attribute_variations(self, concept_name: str) -> dict[str, list[ConceptAttribute]]:
        concept = self.get_or_create(concept_name)
        grouped: dict[str, list[ConceptAttribute]] = {}
        for attribute in concept.attributes:
            if attribute.scope == "concept_level":
                continue
            grouped.setdefault(attribute.name, []).append(attribute)
        return {
            name: attributes
            for name, attributes in grouped.items()
            if len({attribute.value for attribute in attributes}) >= 2
        }

    def add_relation(
        self,
        source_name: str,
        *,
        relation_type: str,
        target_name: str,
        confidence: float,
        evidence_refs: list[str],
    ) -> Concept:
        source = self.get_or_create(source_name)
        self.get_or_create(target_name)
        for existing in source.relations:
            if existing.relation_type == relation_type and existing.target_concept == target_name:
                existing.confidence = min(0.95, max(existing.confidence, confidence))
                for ref in evidence_refs:
                    if ref not in existing.evidence_refs:
                        existing.evidence_refs.append(ref)
                source.evidence_refs.extend(ref for ref in evidence_refs if ref not in source.evidence_refs)
                source.confidence = min(0.95, max(source.confidence, confidence * 0.85))
                source.touch()
                return source

        source.relations.append(
            Relation(
                relation_type=relation_type,
                target_concept=target_name,
                confidence=confidence,
                evidence_refs=evidence_refs,
            )
        )
        source.evidence_refs.extend(ref for ref in evidence_refs if ref not in source.evidence_refs)
        source.confidence = min(0.95, max(source.confidence, confidence * 0.85))
        source.maturity = "early" if source.confidence >= 0.35 else source.maturity
        source.touch()
        return source

    def remove_relations_by_evidence_ref(self, evidence_ref: str) -> list[dict[str, str]]:
        removed = []
        for concept in self.concepts.values():
            kept = []
            for relation in concept.relations:
                if evidence_ref in relation.evidence_refs:
                    removed.append(
                        {
                            "source": concept.name,
                            "relation_type": relation.relation_type,
                            "target": relation.target_concept,
                        }
                    )
                    continue
                kept.append(relation)
            if len(kept) != len(concept.relations):
                concept.relations = kept
                concept.touch()
        return removed

    def add_open_question(self, concept_name: str, question: str, reason: str) -> None:
        concept = self.get_or_create(concept_name)
        if any(item.get("question") == question for item in concept.open_questions):
            return
        concept.open_questions.append({"question": question, "reason": reason})
        concept.touch()

    def record_question_answer(
        self,
        concept_name: str,
        *,
        question: str,
        answer: str,
        evidence_id: str,
        conflicted: bool = False,
    ) -> None:
        concept = self.get_or_create(concept_name)
        for item in concept.open_questions:
            if item.get("question") != question:
                continue
            item["status"] = "conflicted" if conflicted else "answered"
            item["last_answer"] = answer
            item.setdefault("answer_evidence_refs", [])
            if evidence_id not in item["answer_evidence_refs"]:
                item["answer_evidence_refs"].append(evidence_id)
            concept.touch()
            return

        concept.open_questions.append(
            {
                "question": question,
                "reason": "answered_curiosity_question",
                "status": "conflicted" if conflicted else "answered",
                "last_answer": answer,
                "answer_evidence_refs": [evidence_id],
            }
        )
        concept.touch()

    def answer_questions_by_inference(
        self,
        concept_name: str,
        *,
        keyword: str,
        inference_ref: str,
        answer: str,
    ) -> int:
        concept = self.get_or_create(concept_name)
        updated = 0
        for item in concept.open_questions:
            if item.get("status") in self.ANSWERED_QUESTION_STATUSES:
                continue
            if keyword not in item.get("question", ""):
                continue
            item["status"] = "answered_by_inference"
            item["inference_ref"] = inference_ref
            item["inferred_answer"] = answer
            updated += 1
        if updated == 0:
            concept.open_questions.append(
                {
                    "question": f"{concept.name} 是不是都能吃？有没有不能吃或不应该吃的情况？",
                    "reason": "answered_by_reasoning_rule",
                    "status": "answered_by_inference",
                    "inference_ref": inference_ref,
                    "inferred_answer": answer,
                }
            )
            updated = 1
        if updated:
            concept.touch()
        return updated

    def generalize_parent_concepts(self) -> list[dict[str, object]]:
        return self.refresh_category_membership()

    def refresh_category_membership(self) -> list[dict[str, object]]:
        reports = []
        parent_to_children: dict[str, list[Concept]] = {}
        parent_to_counterexamples: dict[str, list[Concept]] = {}
        for concept in self.concepts.values():
            for relation in concept.relations:
                if relation.relation_type == "is-a":
                    parent_to_children.setdefault(relation.target_concept, []).append(concept)
                if relation.relation_type == "is-not-a":
                    parent_to_counterexamples.setdefault(relation.target_concept, []).append(concept)

        parent_names = set(parent_to_children) | set(parent_to_counterexamples)
        for parent_name in parent_names:
            children = parent_to_children.get(parent_name, [])
            counterexamples = parent_to_counterexamples.get(parent_name, [])
            parent = self.get_or_create(parent_name)
            parent.examples = [
                {
                    "concept": child.name,
                    "concept_id": child.concept_id,
                    "relation": "is-a",
                }
                for child in sorted(children, key=lambda item: item.name)
            ]
            parent.counterexamples = [
                {
                    "concept": child.name,
                    "concept_id": child.concept_id,
                    "relation": "is-not-a",
                }
                for child in sorted(counterexamples, key=lambda item: item.name)
            ]
            parent.maturity = "early" if len(parent.examples) >= 2 else parent.maturity
            if parent.examples:
                parent.description = (
                    f"An early parent concept for {parent_name}, abstracted from examples: "
                    + ", ".join(example["concept"] for example in parent.examples)
                    + "."
                )
            if len(children) >= 2:
                self._add_common_parent_attributes(parent, children)
                self.add_open_question(
                    parent_name,
                    f"{parent_name} 的共同特征是什么？这些例子为什么都属于 {parent_name}？",
                    "parent_concept_needs_common_attributes",
                )
            parent.touch()
            reports.append(
                {
                    "parent": parent_name,
                    "examples": [child.name for child in children],
                    "counterexamples": [child.name for child in counterexamples],
                    "example_count": len(parent.examples),
                    "counterexample_count": len(parent.counterexamples),
                }
            )
        return reports

    def resolve_questions_by_relations(self) -> list[dict[str, object]]:
        resolved = []
        for concept in self.concepts.values():
            for relation in concept.relations:
                if relation.relation_type in {"is-a", "is-not-a"}:
                    resolved.extend(self._resolve_classification_questions(concept, relation))
                    resolved.extend(self._resolve_inverse_classification_questions(concept, relation))
                elif relation.relation_type in {"contains", "supports", "made-of", "may_trigger", "related-to", "can_affect"}:
                    resolved.extend(self._resolve_relation_questions(concept, relation))
                    self._add_mechanism_question(concept, relation)
        return resolved

    def refresh_boundary_questions(self) -> list[dict[str, object]]:
        refreshed = []
        for concept in self.concepts.values():
            if not concept.examples or not concept.counterexamples:
                continue
            examples = ", ".join(example["concept"] for example in concept.examples[:3])
            counterexamples = ", ".join(example["concept"] for example in concept.counterexamples[:3])
            question = (
                f"为什么 {examples} 属于 {concept.name}，但 {counterexamples} 不属于？"
                "这个边界由什么决定？"
            )
            before = len(concept.open_questions)
            self.add_open_question(
                concept.name,
                question,
                "positive_negative_boundary_unclear",
            )
            if len(concept.open_questions) != before:
                refreshed.append(
                    {
                        "concept": concept.name,
                        "question": question,
                        "reason": "positive_negative_boundary_unclear",
                    }
                )
        return refreshed

    def all_concepts(self) -> list[Concept]:
        return list(self.concepts.values())

    def _resolve_classification_questions(self, concept: Concept, relation: Relation) -> list[dict[str, object]]:
        resolved = []
        target = relation.target_concept
        for item in concept.open_questions:
            if item.get("status") in self.ANSWERED_QUESTION_STATUSES:
                continue
            question = item.get("question", "")
            if target not in question:
                continue
            if relation.relation_type not in question and not any(marker in question for marker in ["是不是", "会不会", "属于", "分类"]):
                continue
            status = "answered_by_relation" if relation.relation_type == "is-a" else "rejected_by_relation"
            item["status"] = status
            item["relation_type"] = relation.relation_type
            item["relation_target"] = target
            item["relation_evidence_refs"] = list(relation.evidence_refs)
            item["inferred_answer"] = (
                f"{concept.name} {relation.relation_type} {target} 已由关系证据回答。"
            )
            resolved.append(
                {
                    "concept": concept.name,
                    "question": question,
                    "status": status,
                    "relation": relation.relation_type,
                    "target": target,
                }
            )
        if resolved:
            concept.touch()
        return resolved

    def _resolve_inverse_classification_questions(self, concept: Concept, relation: Relation) -> list[dict[str, object]]:
        if relation.relation_type != "is-a":
            return []
        parent = self.get_or_create(relation.target_concept)
        resolved = []
        for item in parent.open_questions:
            if item.get("status") in self.ANSWERED_QUESTION_STATUSES:
                continue
            question = item.get("question", "")
            if concept.name not in question:
                continue
            if not any(marker in question for marker in ["是不是", "会不会", "属于", "分类"]):
                continue
            item["status"] = "answered_by_inverse_relation"
            item["relation_type"] = relation.relation_type
            item["relation_target"] = concept.name
            item["relation_evidence_refs"] = list(relation.evidence_refs)
            item["inferred_answer"] = (
                f"{concept.name} is-a {parent.name} 已说明层级方向；"
                f"{parent.name} 不是因此自动成为 {concept.name}。"
            )
            resolved.append(
                {
                    "concept": parent.name,
                    "question": question,
                    "status": "answered_by_inverse_relation",
                    "relation": relation.relation_type,
                    "target": concept.name,
                }
            )
        if resolved:
            parent.touch()
        return resolved

    def _resolve_relation_questions(self, concept: Concept, relation: Relation) -> list[dict[str, object]]:
        resolved = []
        for item in concept.open_questions:
            if item.get("status") in self.ANSWERED_QUESTION_STATUSES:
                continue
            question = item.get("question", "")
            if relation.target_concept not in question:
                continue
            if relation.relation_type not in question and "关系" not in question:
                continue
            item["status"] = "answered_by_relation"
            item["relation_type"] = relation.relation_type
            item["relation_target"] = relation.target_concept
            item["relation_evidence_refs"] = list(relation.evidence_refs)
            resolved.append(
                {
                    "concept": concept.name,
                    "question": question,
                    "status": "answered_by_relation",
                    "relation": relation.relation_type,
                    "target": relation.target_concept,
                }
            )
        if resolved:
            concept.touch()
        return resolved

    def _add_mechanism_question(self, concept: Concept, relation: Relation) -> None:
        question = (
            f"{concept.name} {relation.relation_type} {relation.target_concept} "
            "这件事为什么重要？它背后的机制或条件是什么？"
        )
        self.add_open_question(
            concept.name,
            question,
            "relation_mechanism_unclear",
        )

    def _add_common_parent_attributes(self, parent: Concept, children: list[Concept]) -> None:
        parent.attributes = [
            attribute for attribute in parent.attributes if not attribute.name.startswith("common_")
        ]
        value_to_children: dict[tuple[str, str], set[str]] = {}
        value_to_evidence: dict[tuple[str, str], list[str]] = {}
        for child in children:
            for attribute in child.attributes:
                if attribute.scope == "concept_level":
                    continue
                key = (attribute.name, attribute.value)
                value_to_children.setdefault(key, set()).add(child.name)
                value_to_evidence.setdefault(key, [])
                for ref in attribute.evidence_refs:
                    if ref not in value_to_evidence[key]:
                        value_to_evidence[key].append(ref)

        for (name, value), supporting_children in value_to_children.items():
            coverage = len(supporting_children) / max(1, len(children))
            if len(supporting_children) < 2 or coverage < 0.8:
                continue
            generalized_name = f"common_{name}"
            generalized_value = (
                f"Many {parent.name} examples share {name}: {value}"
            )
            for existing in parent.attributes:
                if existing.name == generalized_name and existing.value == generalized_value:
                    for ref in value_to_evidence[(name, value)]:
                        if ref not in existing.evidence_refs:
                            existing.evidence_refs.append(ref)
                    existing.confidence = min(0.85, max(existing.confidence, 0.45 + 0.1 * len(supporting_children)))
                    break
            else:
                parent.attributes.append(
                    ConceptAttribute(
                        name=generalized_name,
                        value=generalized_value,
                        confidence=min(0.85, 0.45 + 0.1 * len(supporting_children)),
                        evidence_refs=value_to_evidence[(name, value)],
                        scope="concept_level",
                        generalization_status="generalized_candidate",
                    )
                )

    def apply_evidence_statuses(self, evidence_statuses: dict[str, str]) -> None:
        active_statuses = {"provisional", "confirmed"}
        for concept in self.concepts.values():
            concept.attributes = [
                attribute
                for attribute in concept.attributes
                if self._keep_supported(
                    attribute.evidence_refs,
                    evidence_statuses,
                    active_statuses,
                    min_active_refs=2 if attribute.scope == "concept_level" else 1,
                )
            ]
            concept.relations = [
                relation
                for relation in concept.relations
                if self._keep_supported(relation.evidence_refs, evidence_statuses, active_statuses)
            ]
            concept.evidence_refs = [
                ref
                for ref in concept.evidence_refs
                if evidence_statuses.get(ref, "provisional") in active_statuses
            ]
            concept.touch()

    @staticmethod
    def _key(name: str) -> str:
        return name.strip().lower()

    def _keep_supported(
        self,
        evidence_refs: list[str],
        evidence_statuses: dict[str, str],
        active_statuses: set[str],
        min_active_refs: int = 1,
    ) -> bool:
        active_refs = [
            ref
            for ref in evidence_refs
            if evidence_statuses.get(ref, "provisional") in active_statuses
        ]
        return len(active_refs) >= min_active_refs

    def _dedupe_concept(self, concept: Concept) -> None:
        attribute_map = {}
        for attribute in concept.attributes:
            key = (attribute.name, attribute.value)
            if key not in attribute_map:
                attribute_map[key] = attribute
                continue
            existing = attribute_map[key]
            existing.confidence = max(existing.confidence, attribute.confidence)
            for ref in attribute.evidence_refs:
                if ref not in existing.evidence_refs:
                    existing.evidence_refs.append(ref)
        concept.attributes = list(attribute_map.values())

        relation_map = {}
        for relation in concept.relations:
            key = (relation.relation_type, relation.target_concept)
            if key not in relation_map:
                relation_map[key] = relation
                continue
            existing = relation_map[key]
            existing.confidence = max(existing.confidence, relation.confidence)
            for ref in relation.evidence_refs:
                if ref not in existing.evidence_refs:
                    existing.evidence_refs.append(ref)
        concept.relations = list(relation_map.values())

        question_map = {}
        for question in concept.open_questions:
            question_map.setdefault(question.get("question"), question)
        concept.open_questions = list(question_map.values())
