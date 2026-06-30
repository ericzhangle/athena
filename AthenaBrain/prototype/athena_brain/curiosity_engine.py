from __future__ import annotations

import hashlib
import re

from .concept_graph import ConceptGraph
from .models import Concept
from .similarity_engine import SimilarityEngine


class CuriosityEngine:
    """Selects useful questions from Athena's current cognitive gaps.

    Curiosity is driven by Athena's current memory tree. It should not ask from
    external categories Athena has not learned yet; it tries to place new
    concepts into existing relations, attributes and parent concepts.
    """

    def __init__(self) -> None:
        self.similarity_engine = SimilarityEngine()
        self.resolved_statuses = {
            "answered",
            "answered_by_inference",
            "answered_by_reference",
            "answered_by_relation",
            "answered_by_inverse_relation",
            "rejected_by_relation",
        }

    def propose_questions(
        self,
        graph: ConceptGraph,
        *,
        limit: int = 6,
        focus_concepts: list[str] | None = None,
    ) -> list[dict[str, object]]:
        candidates: list[dict[str, object]] = []
        focus_set = {name for name in (focus_concepts or []) if name}
        concepts = [
            concept
            for concept in graph.all_concepts()
            if not focus_set or concept.name in focus_set
        ]
        for concept in concepts:
            candidates.extend(self._cognitive_gap_candidates(graph, concept))

        deduped: dict[tuple[object, object], dict[str, object]] = {}
        for candidate in candidates:
            key = (candidate["concept"], candidate["question"])
            existing = deduped.get(key)
            if existing is None or float(candidate["priority"]) > float(existing["priority"]):
                deduped[key] = candidate

        ranked = sorted(
            deduped.values(),
            key=lambda item: (
                -float(item["priority"]),
                str(item.get("domain", "")),
                str(item["concept"]),
                str(item["question"]),
            ),
        )
        return self._diversify(ranked, limit=limit)

    def question_id(self, concept_name: str, question: str) -> str:
        digest = hashlib.sha1(f"{concept_name}:{question}".encode("utf-8")).hexdigest()[:12]
        return f"curiosity_{digest}"

    def normalize_answer(self, answer: str) -> str:
        return " ".join(answer.strip().lower().split())

    def infer_attribute_from_answer(
        self,
        *,
        question: str,
        answer: str,
    ) -> tuple[str, str] | None:
        question_text = question.lower()
        answer_text = answer.strip()
        if not answer_text:
            return None

        if "吃" in question or "edible" in question_text or "eat" in question_text:
            return ("edibility", self._edibility_value(answer_text))
        if "颜色" in question or "color" in question_text:
            return ("color", f"The user says possible colors include: {answer_text}.")
        if "形状" in question or "shape" in question_text:
            return ("shape", f"The user says possible shapes include: {answer_text}.")
        if "边界" in question or "属于" in question or "例子" in question:
            return ("boundary_note", f"The user says about the boundary: {answer_text}.")
        return ("user_explanation", f"The user answered: {answer_text}.")

    def discover_concepts_from_answer(
        self,
        *,
        current_concept: str,
        answer: str,
    ) -> list[dict[str, str]]:
        discoveries: list[dict[str, str]] = []
        normalized_current = current_concept.lower()
        answer_text = answer.strip()
        if not answer_text:
            return discoveries

        for match in re.finditer(r"([\u4e00-\u9fffA-Za-z]+)是不能吃的", answer_text):
            concept = self._normalize_discovered_concept(match.group(1))
            if concept.lower() == normalized_current:
                continue
            discoveries.append(
                {
                    "concept": concept,
                    "attribute_name": "edibility",
                    "attribute_value": f"The user says {concept} cannot be eaten.",
                    "question": f"{concept} 是什么？它为什么不能吃？它还有哪些特性？",
                    "reason": "new_concept_from_curiosity_answer",
                }
            )

        for match in re.finditer(r"(?:是|因为是)([\u4e00-\u9fffA-Za-z]+)(?:做的|制成的|制作的)", answer_text):
            concept = self._normalize_discovered_concept(match.group(1))
            if concept.lower() == normalized_current:
                continue
            discoveries.append(
                {
                    "concept": concept,
                    "attribute_name": "material_property",
                    "attribute_value": f"The user says {concept} can be used as a material.",
                    "question": f"{concept} 是什么材料？它有哪些特性？",
                    "reason": "material_concept_from_curiosity_answer",
                }
            )

        return self._dedupe_discoveries(discoveries)

    def _cognitive_gap_candidates(self, graph: ConceptGraph, concept: Concept) -> list[dict[str, object]]:
        candidates: list[dict[str, object]] = []
        candidates.extend(self._questions_from_open_questions(concept))
        candidates.extend(self._identity_gap_questions(concept))
        candidates.extend(self._memory_tree_classification_questions(graph, concept))
        candidates.extend(self._composition_gap_questions(concept))
        candidates.extend(self._role_gap_questions(concept))
        candidates.extend(self._mechanism_gap_questions(concept))
        candidates.extend(self._relation_gap_questions(graph, concept))
        candidates.extend(self._variation_gap_questions(concept))
        candidates.extend(self._boundary_gap_questions(concept))
        return [self._score_candidate(concept, candidate) for candidate in candidates]

    def _questions_from_open_questions(self, concept: Concept) -> list[dict[str, object]]:
        questions = []
        for item in concept.open_questions:
            if item.get("status") in self.resolved_statuses:
                continue
            reason = item.get("reason", "open_question")
            if reason == "function_gap" and not self._has_known_functional_role(concept):
                continue
            priority = 0.78 if item.get("status") == "conflicted" else 0.58
            if reason == "curiosity_answer_conflict":
                priority = 0.9
            if reason in {"new_concept_from_curiosity_answer", "material_concept_from_curiosity_answer"}:
                priority = 0.68
            questions.append(
                self._candidate(
                    concept,
                    item.get("question", ""),
                    reason,
                    priority,
                    domain=self._domain_from_reason(reason),
                    status=item.get("status", "open"),
                )
            )
        return questions

    def _identity_gap_questions(self, concept: Concept) -> list[dict[str, object]]:
        has_identity = any(attribute.name in {"identity", "definition", "category"} for attribute in concept.attributes)
        if has_identity or (concept.attributes and concept.relations and concept.maturity != "seed"):
            return []
        question = f"{concept.name} 到底是什么？它最关键、最能区分它的特征是什么？"
        if self._has_recorded_question(concept, question) or self._has_domain_question(concept, "identity"):
            return []
        return [self._candidate(concept, question, "identity_gap", 0.66, domain="identity")]

    def _composition_gap_questions(self, concept: Concept) -> list[dict[str, object]]:
        attribute_names = {attribute.name for attribute in concept.attributes}
        if "material_property" not in attribute_names:
            return []
        question = f"{concept.name} 是由什么构成的？它有哪些材料或物理特性？"
        if self._has_recorded_question(concept, question) or self._has_domain_question(concept, "composition"):
            return []
        return [self._candidate(concept, question, "composition_gap", 0.74, domain="composition")]

    def _memory_tree_classification_questions(
        self,
        graph: ConceptGraph,
        concept: Concept,
    ) -> list[dict[str, object]]:
        if self._has_parent_category(concept):
            return []
        similarity_questions = self._similarity_classification_questions(graph, concept)
        if similarity_questions:
            return similarity_questions
        categories = self._known_category_candidates(graph, exclude=concept.name)
        questions = []
        for category in categories[:2]:
            if self._has_negative_category(concept, category):
                continue
            if self._known_child_of(graph, child_name=category, parent_name=concept.name):
                continue
            question = f"{concept.name} 是不是一种 {category}，还是和 {category} 不同？"
            if self._has_recorded_question(concept, question):
                continue
            questions.append(
                self._candidate(
                    concept,
                    question,
                    "classify_against_known_category",
                    0.56,
                    domain="classification",
                )
            )
        return questions

    def _similarity_classification_questions(
        self,
        graph: ConceptGraph,
        concept: Concept,
    ) -> list[dict[str, object]]:
        questions = []
        for candidate in self.similarity_engine.candidate_parent_questions(graph, concept):
            shared = ", ".join(candidate["shared_features"][:3])
            question = (
                f"{concept.name} 和一些已知 {candidate['parent']} 例子有相似特征"
                f"（{shared}）。{concept.name} 会不会也是一种 {candidate['parent']}？"
            )
            if self._has_recorded_question(concept, question):
                continue
            questions.append(
                self._candidate(
                    concept,
                    question,
                    "similarity_based_candidate_category",
                    0.74 + min(0.12, float(candidate["score"]) * 0.12),
                    domain="classification",
                )
            )
        return questions

    def _role_gap_questions(self, concept: Concept) -> list[dict[str, object]]:
        questions = []
        for relation in concept.relations:
            if relation.relation_type not in {"supports", "can_affect", "may_trigger"}:
                continue
            question = f"{concept.name} {relation.relation_type} {relation.target_concept} 这件事为什么重要？它会带来什么影响？"
            if not self._has_recorded_question(concept, question):
                questions.append(self._candidate(concept, question, "relation_mechanism_unclear", 0.62, domain="relation"))
        return questions

    def _mechanism_gap_questions(self, concept: Concept) -> list[dict[str, object]]:
        questions = []
        if self._has_known_inedible_answer(concept):
            question = f"为什么 {concept.name} 不能吃？这个原因和我已经知道的哪些概念有关？"
            if (
                not self._has_recorded_question(concept, question)
                and not self._has_question_containing(concept, ["为什么", "不能吃"])
            ):
                questions.append(self._candidate(concept, question, "mechanism_gap", 0.78, domain="mechanism"))
        elif self._has_observed_edible_answer(concept) and not self._has_inferred_edibility(concept):
            question = f"{concept.name} 能吃这件事有什么条件或例外？什么时候不能简单推广？"
            if not self._has_recorded_question(concept, question):
                questions.append(self._candidate(concept, question, "condition_gap", 0.46, domain="mechanism"))
        return questions

    def _relation_gap_questions(self, graph: ConceptGraph, concept: Concept) -> list[dict[str, object]]:
        questions = []
        for relation in concept.relations[:2]:
            if relation.relation_type in {"is-a", "is-not-a"}:
                continue
            question = (
                f"{concept.name} 和 {relation.target_concept} 之间的“{relation.relation_type}”关系，"
                "在我已有知识里意味着什么？"
            )
            if not self._has_recorded_question(concept, question):
                questions.append(
                    self._candidate(concept, question, "relation_meaning_gap", 0.5, domain="relation")
                )
        incoming_by_relation: dict[str, list[str]] = {}
        for source in graph.all_concepts():
            if source.name == concept.name:
                continue
            for relation in source.relations:
                if relation.target_concept != concept.name:
                    continue
                if relation.relation_type in {"is-a", "is-not-a"}:
                    continue
                incoming_by_relation.setdefault(relation.relation_type, [])
                if source.name not in incoming_by_relation[relation.relation_type]:
                    incoming_by_relation[relation.relation_type].append(source.name)
                break
        for relation_type, sources in sorted(incoming_by_relation.items()):
            source_text = ", ".join(sources[:4])
            question = (
                f"{concept.name} 被 {source_text} 等概念通过“{relation_type}”联系起来。"
                f"这说明 {concept.name} 在这些关系里扮演什么角色？"
            )
            if not self._has_recorded_question(concept, question):
                questions.append(
                    self._candidate(concept, question, "incoming_relation_role_gap", 0.64, domain="relation")
                )
        return questions

    def _variation_gap_questions(self, concept: Concept) -> list[dict[str, object]]:
        questions = []
        for attribute_name in ["shape", "color", "surface"]:
            values = [
                attribute.value
                for attribute in concept.attributes
                if attribute.name == attribute_name and attribute.scope != "inferred"
            ]
            if not values:
                continue
            question = f"{concept.name} 的 {attribute_name} 会怎样变化？哪些变化仍然属于它，哪些变化会改变它的类别？"
            if not self._has_recorded_question(concept, question):
                questions.append(
                    self._candidate(
                        concept,
                        question,
                        f"{attribute_name}_variation_gap",
                        0.44 if len(values) == 1 else 0.62,
                        domain="variation",
                    )
                )
        return questions

    def _boundary_gap_questions(self, concept: Concept) -> list[dict[str, object]]:
        questions = []
        if concept.examples and concept.counterexamples:
            examples = ", ".join(example["concept"] for example in concept.examples[:3])
            counterexamples = ", ".join(example["concept"] for example in concept.counterexamples[:3])
            question = (
                f"为什么 {examples} 属于 {concept.name}，但 {counterexamples} 不属于？"
                "这个边界由什么决定？"
            )
            if self._has_recorded_question(concept, question):
                return questions
            questions.append(
                self._candidate(concept, question, "positive_negative_boundary_unclear", 0.86, domain="boundary")
            )
        elif concept.examples:
            question = f"除了这些例子，什么样的东西也可以属于 {concept.name}？"
            questions.append(self._candidate(concept, question, "more_examples_needed", 0.5, domain="boundary"))
        return questions

    def _candidate(
        self,
        concept: Concept,
        question: str,
        reason: str,
        priority: float,
        *,
        domain: str,
        status: str = "open",
    ) -> dict[str, object]:
        return {
            "question_id": self.question_id(concept.name, question),
            "concept": concept.name,
            "question": question,
            "reason": reason,
            "priority": priority,
            "domain": domain,
            "status": status,
        }

    def _score_candidate(self, concept: Concept, candidate: dict[str, object]) -> dict[str, object]:
        uncertainty = 0.16 if concept.maturity in {"seed", "early"} else 0.04
        novelty = 0.12 if len(concept.evidence_refs) <= 2 else 0.0
        conflict = 0.2 if candidate.get("status") == "conflicted" else 0.0
        abstraction = 0.16 if candidate.get("domain") in {"boundary", "relation", "mechanism"} else 0.04
        redundancy_penalty = self._redundancy_penalty(concept, str(candidate["question"]), str(candidate["domain"]))
        candidate["priority"] = round(
            max(0.05, min(0.98, float(candidate["priority"]) + uncertainty + novelty + conflict + abstraction - redundancy_penalty)),
            3,
        )
        candidate["score_factors"] = {
            "base": candidate["reason"],
            "uncertainty": uncertainty,
            "novelty": novelty,
            "conflict": conflict,
            "abstraction": abstraction,
            "redundancy_penalty": redundancy_penalty,
        }
        return candidate

    def _diversify(self, ranked: list[dict[str, object]], *, limit: int) -> list[dict[str, object]]:
        selected: list[dict[str, object]] = []
        domain_counts: dict[str, int] = {}
        concept_counts: dict[str, int] = {}
        for candidate in ranked:
            domain = str(candidate.get("domain", "unknown"))
            concept = str(candidate["concept"])
            if domain_counts.get(domain, 0) >= 2:
                continue
            if concept_counts.get(concept, 0) >= 2:
                continue
            selected.append(candidate)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            concept_counts[concept] = concept_counts.get(concept, 0) + 1
            if len(selected) >= limit:
                return selected

        for candidate in ranked:
            if candidate in selected:
                continue
            selected.append(candidate)
            if len(selected) >= limit:
                return selected
        return selected

    def _domain_from_reason(self, reason: str) -> str:
        if "boundary" in reason or "example" in reason:
            return "boundary"
        if "relation" in reason:
            return "relation"
        if "classify" in reason:
            return "classification"
        if "material" in reason or "composition" in reason:
            return "composition"
        if "conflict" in reason:
            return "conflict"
        if "variation" in reason:
            return "variation"
        if "identity" in reason or "new_concept" in reason:
            return "identity"
        return "open"

    def _redundancy_penalty(self, concept: Concept, question: str, domain: str) -> float:
        penalty = 0.0
        for item in concept.open_questions:
            existing = item.get("question", "")
            if existing == question:
                penalty += 0.12
            if domain != "open" and domain == self._domain_from_reason(item.get("reason", "")):
                penalty += 0.04
        return min(0.24, penalty)

    def _has_recorded_question(self, concept: Concept, question: str) -> bool:
        return any(item.get("question") == question for item in concept.open_questions)

    def _has_domain_question(self, concept: Concept, domain: str) -> bool:
        return any(
            self._domain_from_reason(item.get("reason", "")) == domain
            for item in concept.open_questions
            if item.get("status") not in self.resolved_statuses
        )

    def _has_question_containing(self, concept: Concept, markers: list[str]) -> bool:
        return any(
            all(marker in item.get("question", "") for marker in markers)
            for item in concept.open_questions
            if item.get("status") not in self.resolved_statuses
        )

    def _has_known_inedible_answer(self, concept: Concept) -> bool:
        for attribute in concept.attributes:
            if attribute.name not in {"edibility", "use"}:
                continue
            value = attribute.value.lower()
            if any(
                marker in value
                for marker in [
                    "cannot be eaten",
                    "not edible",
                    "not food",
                    "不能吃",
                    "不可以吃",
                    "不可食用",
                ]
            ):
                return True
        return False

    def _has_observed_edible_answer(self, concept: Concept) -> bool:
        for attribute in concept.attributes:
            if attribute.name not in {"edibility", "use"}:
                continue
            if attribute.scope == "inferred":
                continue
            value = attribute.value.lower()
            if any(marker in value for marker in ["can be eaten", "usually edible", "能吃", "可以吃"]):
                return True
        return False

    def _has_inferred_edibility(self, concept: Concept) -> bool:
        return any(
            attribute.name == "edibility"
            and attribute.scope == "inferred"
            for attribute in concept.attributes
        )

    def _has_known_functional_role(self, concept: Concept) -> bool:
        if any(attribute.name in {"use", "function"} for attribute in concept.attributes):
            return True
        return any(
            relation.relation_type in {"supports", "can_affect", "may_trigger"}
            for relation in concept.relations
        )

    def _has_parent_category(self, concept: Concept) -> bool:
        return any(relation.relation_type == "is-a" for relation in concept.relations)

    def _has_negative_category(self, concept: Concept, category: str) -> bool:
        return any(
            relation.relation_type == "is-not-a"
            and relation.target_concept == category
            for relation in concept.relations
        )

    def _known_category_candidates(self, graph: ConceptGraph, *, exclude: str) -> list[str]:
        categories = set()
        for concept in graph.all_concepts():
            if concept.name == exclude:
                continue
            if concept.examples:
                categories.add(concept.name)
            for relation in concept.relations:
                if relation.relation_type == "is-a" and relation.target_concept != exclude:
                    categories.add(relation.target_concept)
        return sorted(categories)

    def _known_child_of(self, graph: ConceptGraph, *, child_name: str, parent_name: str) -> bool:
        child = graph.get_or_create(child_name)
        return any(
            relation.relation_type == "is-a"
            and relation.target_concept == parent_name
            for relation in child.relations
        )

    def _normalize_discovered_concept(self, value: str) -> str:
        aliases = {
            "塑料": "Plastic",
            "金属": "Metal",
            "木头": "Wood",
            "玻璃": "Glass",
        }
        cleaned = value.strip(" ，,。.!！?？")
        return aliases.get(cleaned, cleaned.title() if cleaned.isascii() else cleaned)

    def _dedupe_discoveries(self, discoveries: list[dict[str, str]]) -> list[dict[str, str]]:
        seen = set()
        deduped = []
        for item in discoveries:
            key = (item["concept"], item["attribute_name"], item["attribute_value"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _edibility_value(self, answer: str) -> str:
        lowered = answer.lower()
        if any(marker in answer for marker in ["不一定", "不是都", "有些不能", "不能吃", "不应该吃"]):
            return f"edibility has exceptions: {answer}."
        if any(marker in lowered for marker in ["not always", "some cannot", "cannot eat"]):
            return f"edibility has exceptions: {answer}."
        if any(marker in answer for marker in ["都能吃", "可以吃", "能吃"]):
            return f"can usually be eaten: {answer}."
        return f"The user says about edibility: {answer}."
