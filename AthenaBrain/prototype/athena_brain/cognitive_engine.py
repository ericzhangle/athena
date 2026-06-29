from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .attribute_normalizer import AttributeNormalizer
from .cognitive_integration_engine import CognitiveIntegrationEngine
from .concept_graph import ConceptGraph
from .curiosity_engine import CuriosityEngine
from .evidence_ledger import EvidenceLedger
from .inquiry_loop_engine import InquiryLoopEngine
from .knowledge_ingestion_engine import KnowledgeIngestionEngine
from .models import Claim, Experience, Rule, concept_from_dict, new_id, rule_from_dict
from .perception import PerceptionInterface
from .reasoning_engine import ReasoningEngine
from .sleep_engine import SleepEngine
from .state_manager import StateManager
from .store import JsonMemoryStore


class CognitiveEngine:
    """Coordinates the first BabyBrain learning loop."""

    def __init__(self, data_root: str | Path) -> None:
        self.store = JsonMemoryStore(data_root)
        self.evidence_ledger = EvidenceLedger(self.store)
        self.state_manager = StateManager()
        self.perception_interface = PerceptionInterface()
        self.attribute_normalizer = AttributeNormalizer()
        self.curiosity_engine = CuriosityEngine()
        self.knowledge_ingestion_engine = KnowledgeIngestionEngine()
        self.inquiry_loop_engine = InquiryLoopEngine()
        self.cognitive_integration_engine = CognitiveIntegrationEngine()
        self.reasoning_engine = ReasoningEngine()
        self.rules: dict[str, Rule] = {}
        self.graph = ConceptGraph()
        self._load_existing_concepts()
        self._load_existing_rules()
        self.sleep_engine = SleepEngine()

    def learn_from_guided_example(
        self,
        *,
        user_statement: str,
        image_path: str,
        sample_id: str,
        perception_features: list[dict[str, object]],
        user_feedback: list[dict[str, Any]],
        source_identity: str = "user",
        source_diversity: str = "single_user",
        independence_score: float = 0.5,
    ) -> dict[str, Any]:
        relation = self._extract_relation(user_statement)
        source_concept = relation["source"] if relation else self._guess_concept(user_statement)
        target_concept = relation["target"] if relation else None

        external_state = self.state_manager.create_external_state(
            current_task=f"learn_{source_concept.lower()}_from_guided_example",
            user_text=user_statement,
            image_path=image_path,
        )
        self.store.save("states", external_state.state_id, external_state)

        candidate_concepts = [source_concept]
        relation_targets = [target_concept] if target_concept else []
        internal_state = self.state_manager.create_initial_internal_state(
            candidate_concepts=candidate_concepts,
            relation_targets=relation_targets,
        )
        self.store.save("states", internal_state.state_id, internal_state)

        perception = self.perception_interface.perceive_image(
            image_path,
            features=perception_features,
            sample_id=sample_id,
            hypotheses=[
                {
                    "hypothesis": source_concept,
                    "source": "user_statement_or_vision_label",
                    "confidence": 0.3,
                    "status": "unverified",
                }
            ],
        )
        self.store.save("perceptions", perception.perception_id, perception)

        feature_evidence_refs = {}
        for feature in perception.features:
            evidence = self.evidence_ledger.add_evidence(
                claim=Claim(
                    statement=f"{source_concept} observed {feature.category}: {feature.value}",
                    subject=source_concept,
                    predicate=f"observed_{feature.category}",
                    object=feature.value,
                ),
                source_type="direct_perception",
                source_identity="vision_interface",
                refs=[perception.perception_id, f"sample:{sample_id}"],
                confidence=min(0.8, feature.confidence),
                sample_id=sample_id,
            )
            feature_evidence_refs[(feature.category, feature.value)] = evidence.evidence_id

        internal_state = self.state_manager.update_after_perception(
            internal_state,
            perception=perception,
            candidate_concepts=candidate_concepts,
        )
        self.store.save("states", internal_state.state_id, internal_state)

        experience = Experience(
            raw_inputs=[
                {"type": "text", "speaker": "user", "content": user_statement},
                {"type": "image", "path": image_path, "sample_id": sample_id},
            ],
            perception_refs=[perception.perception_id],
            athena_questions=internal_state.pending_questions,
            user_feedback=user_feedback,
            tags=["phase1", source_concept.lower(), "guided_learning"],
            sample_id=sample_id,
            source_identity=source_identity,
            source_diversity=source_diversity,
            independence_score=independence_score,
        )
        self.store.save("experiences", experience.experience_id, experience)

        relation_evidence_id = None
        if relation:
            relation_evidence = self.evidence_ledger.add_evidence(
                claim=Claim(
                    statement=user_statement,
                    subject=source_concept,
                    predicate=relation["relation_type"],
                    object=target_concept,
                ),
                source_type="user_statement",
                source_identity=source_identity,
                refs=[experience.experience_id],
                confidence=0.7,
                sample_id=sample_id,
            )
            relation_evidence_id = relation_evidence.evidence_id

        report = self.sleep_engine.consolidate(
            graph=self.graph,
            experience=experience,
            perception=perception,
            source_concept=source_concept,
            target_concept=target_concept,
            relation_type=relation["relation_type"] if relation else None,
            feature_evidence_refs=feature_evidence_refs,
            relation_evidence_id=relation_evidence_id,
            evidence_statuses=self.evidence_ledger.status_map(),
            evidence_sample_ids=self.evidence_ledger.sample_id_map(),
        )
        self.store.save("reports", str(report["sleep_report_id"]), report)

        concept = self.graph.get_or_create(source_concept)
        concept.description = self._build_description(source_concept, target_concept)
        concept.touch()
        integration_report = self._integrate_cognition("guided_example_learning")
        self._save_all_concepts()

        response = self.describe_concept(source_concept)

        return {
            "external_state_id": external_state.state_id,
            "internal_state_id": internal_state.state_id,
            "perception_id": perception.perception_id,
            "experience_id": experience.experience_id,
            "sleep_report_id": report["sleep_report_id"],
            "integration_report_id": integration_report["integration_report_id"],
            "concept_id": concept.concept_id,
            "response": response,
        }

    def describe_concept(self, concept_name: str) -> str:
        concept = self.graph.get_or_create(concept_name)
        lines = [
            f"我目前对 {concept.display_name or concept.name} 的理解还处在 {concept.maturity} 阶段。",
            "这个理解来自已经记录的经历和感知证据，而不是百科定义。",
        ]

        if concept.attributes:
            generalized = [
                attribute
                for attribute in concept.attributes
                if attribute.scope == "concept_level"
                and attribute.generalization_status
                in {"generalized_candidate", "generalized_attribute"}
            ]
            if generalized:
                lines.append("我已经形成的概念级抽象包括：")
                for attribute in generalized[:3]:
                    label = (
                        "较稳定"
                        if attribute.generalization_status == "generalized_attribute"
                        else "候选"
                    )
                    lines.append(f"- {attribute.value}（{label}，置信度 {attribute.confidence:.2f}）")

            grouped_attributes: dict[str, list[Any]] = {}
            for attribute in concept.attributes:
                if attribute.scope == "concept_level":
                    continue
                grouped_attributes.setdefault(attribute.name, []).append(attribute)

            if grouped_attributes:
                lines.append("我目前观察到的候选特征包括：")
                for name, attributes in list(grouped_attributes.items())[:5]:
                    values = "；".join(
                        f"{attribute.value}（置信度 {attribute.confidence:.2f}）"
                        for attribute in attributes[:3]
                    )
                    if len(attributes) > 1:
                        comparison_mode = self.attribute_normalizer.normalize(
                            name,
                            attributes[0].value,
                        )["comparison_mode"]
                        if comparison_mode == "compatible_traits":
                            lines.append(f"- {name}: 我已经观察到可兼容的补充描述：{values}")
                        else:
                            lines.append(f"- {name}: 我已经观察到多种表现：{values}")
                    else:
                        lines.append(f"- {name}: {values}")

        if concept.examples:
            examples = ", ".join(example["concept"] for example in concept.examples[:6])
            lines.append(f"我目前把这些概念作为 {concept.name} 的例子：{examples}。")

        if concept.counterexamples:
            counterexamples = ", ".join(
                example["concept"] for example in concept.counterexamples[:6]
            )
            lines.append(f"我目前也记录了这些反例/边界例：{counterexamples}。")

        if concept.relations:
            lines.append("我目前记录到的候选关系包括：")
            for relation in concept.relations:
                lines.append(
                    f"- {concept.name} {relation.relation_type} {relation.target_concept}"
                    f"（置信度 {relation.confidence:.2f}，来自证据）"
                )

        if concept.open_questions:
            lines.append("我还不确定的问题包括：")
            for question in concept.open_questions[:3]:
                lines.append(f"- {question['question']}")

        return "\n".join(lines)

    def propose_curiosity_questions(self, *, limit: int = 6) -> list[dict[str, object]]:
        return self.curiosity_engine.propose_questions(self.graph, limit=limit)

    def run_inquiry_loop(self, *, max_steps: int = 10) -> dict[str, object]:
        report = self.inquiry_loop_engine.run(self, max_steps=max_steps)
        self.store.save("reports", str(report["inquiry_report_id"]), report)
        return report

    def ingest_knowledge_text(
        self,
        *,
        text: str,
        source_identity: str = "user_knowledge_text",
    ) -> dict[str, Any]:
        text_ref = new_id("knowledge_text")
        claims = self.knowledge_ingestion_engine.extract_claims(text)
        experience = Experience(
            raw_inputs=[{"type": "text", "speaker": "user", "content": text, "ref": text_ref}],
            perception_refs=[],
            athena_questions=[],
            user_feedback=[],
            tags=["knowledge_ingestion", "article_text"],
            source_identity=source_identity,
            source_diversity="single_text_source",
            independence_score=0.45,
        )
        self.store.save("experiences", experience.experience_id, experience)

        updated_concepts = set()
        evidence_ids = []
        for claim_data in claims:
            evidence = self.evidence_ledger.add_evidence(
                claim=Claim(
                    statement=str(claim_data["statement"]),
                    subject=str(claim_data["subject"]),
                    predicate=str(claim_data["predicate"]),
                    object=str(claim_data["object"]),
                ),
                source_type="user_knowledge_text",
                source_identity=source_identity,
                refs=[text_ref, experience.experience_id],
                confidence=0.58,
            )
            evidence_ids.append(evidence.evidence_id)
            subject = str(claim_data["subject"])
            updated_concepts.add(subject)

            if claim_data["kind"] == "attribute":
                self.graph.add_attribute(
                    subject,
                    attribute_name=str(claim_data["attribute_name"]),
                    value=str(claim_data["attribute_value"]),
                    confidence=0.5,
                    evidence_refs=[evidence.evidence_id],
                    scope="knowledge_text",
                    generalization_status="provisional_from_text",
                )
            elif claim_data["kind"] == "relation":
                target = str(claim_data["target"])
                self.graph.add_relation(
                    subject,
                    relation_type=str(claim_data["relation_type"]),
                    target_name=target,
                    confidence=0.5,
                    evidence_refs=[evidence.evidence_id],
                )
                updated_concepts.add(target)
            else:
                concept = self.graph.get_or_create(subject)
                concept.description = (
                    concept.description
                    if concept.description and not concept.description.startswith("Early concept candidate")
                    else f"An early concept mentioned in a knowledge text: {subject}."
                )
                concept.touch()

            for question in claim_data.get("questions", []):
                self.graph.add_open_question(
                    subject,
                    str(question["question"]),
                    str(question["reason"]),
                )

        integration_report = self._integrate_cognition("knowledge_ingestion")
        self._save_all_concepts()
        report = {
            "report_id": new_id("knowledge_ingestion_report"),
            "text_ref": text_ref,
            "experience_id": experience.experience_id,
            "claim_count": len(claims),
            "evidence_count": len(evidence_ids),
            "updated_concepts": sorted(updated_concepts),
            "generated_questions": self.propose_curiosity_questions(limit=10),
            "integration_report_id": integration_report["integration_report_id"],
            "integration": integration_report,
            "claims": claims,
        }
        self.store.save("reports", report["report_id"], report)
        return report

    def answer_curiosity_question(
        self,
        *,
        concept_name: str,
        question: str,
        answer: str,
        source_identity: str = "user",
    ) -> dict[str, Any]:
        concept_name = self._normalize_concept_name(concept_name)
        question_id = self.curiosity_engine.question_id(concept_name, question)
        predicate = f"curiosity_answer:{question_id}"
        normalized_answer = self.curiosity_engine.normalize_answer(answer)

        existing_answers = self.evidence_ledger.find_claims(
            subject=concept_name,
            predicate=predicate,
        )
        conflicting_evidence = [
            item
            for item in existing_answers
            if self.evidence_ledger.is_active(item.evidence_id)
            and item.claim.object != normalized_answer
        ]

        evidence = self.evidence_ledger.add_evidence(
            claim=Claim(
                statement=f"{source_identity} answered Athena's question: {question} -> {answer}",
                subject=concept_name,
                predicate=predicate,
                object=normalized_answer,
            ),
            source_type="user_curiosity_answer",
            source_identity=source_identity,
            refs=[question_id],
            confidence=0.65,
        )

        disputed_ids = []
        for item in conflicting_evidence:
            disputed = self.evidence_ledger.dispute(
                item.evidence_id,
                reason=(
                    f"New answer {answer!r} conflicts with previous answer "
                    f"{item.claim.object!r} for question {question!r}."
                ),
            )
            if disputed:
                disputed_ids.append(disputed.evidence_id)

        inferred_attribute = self.curiosity_engine.infer_attribute_from_answer(
            question=question,
            answer=answer,
        )
        if inferred_attribute:
            attribute_name, value = inferred_attribute
            self.graph.add_attribute(
                concept_name,
                attribute_name=attribute_name,
                value=value,
                confidence=0.55,
                evidence_refs=[evidence.evidence_id],
            )

        discovered_concepts = self.curiosity_engine.discover_concepts_from_answer(
            current_concept=concept_name,
            answer=answer,
        )
        for discovery in discovered_concepts:
            discovered = self.graph.get_or_create(discovery["concept"])
            discovered.description = (
                f"An early concept for {discovery['concept']}, discovered from "
                f"a user answer about {concept_name}."
            )
            self.graph.add_attribute(
                discovery["concept"],
                attribute_name=discovery["attribute_name"],
                value=discovery["attribute_value"],
                confidence=0.5,
                evidence_refs=[evidence.evidence_id],
            )
            self.graph.add_open_question(
                discovery["concept"],
                discovery["question"],
                discovery["reason"],
            )
            self.graph.add_open_question(
                concept_name,
                (
                    f"我从你的回答里发现了一个新概念 {discovery['concept']}。"
                    f"它和 {concept_name} 的关系是什么？"
                ),
                "new_concept_relation_needs_clarification",
            )
            discovered.touch()

        has_conflict = bool(disputed_ids)
        self.graph.record_question_answer(
            concept_name,
            question=question,
            answer=answer,
            evidence_id=evidence.evidence_id,
            conflicted=has_conflict,
        )

        if has_conflict:
            self.graph.add_open_question(
                concept_name,
                (
                    f"关于 {concept_name}，我对同一个问题收到了不同回答："
                    f"“{question}”。这些回答是否都有条件成立，还是其中一个需要修正？"
                ),
                "curiosity_answer_conflict",
            )

        new_rules = self.reasoning_engine.extract_rules_from_answer(
            answer=answer,
            source_evidence_id=evidence.evidence_id,
        )
        for rule in new_rules:
            self.rules[rule.rule_id] = rule
            self.store.save("rules", rule.rule_id, rule)
        inferences = self.reasoning_engine.apply_rules(
            self.graph,
            list(self.rules.values()),
        )

        integration_report = self._integrate_cognition("curiosity_answer")
        self._save_all_concepts()
        return {
            "concept": concept_name,
            "question_id": question_id,
            "question": question,
            "answer": answer,
            "answer_evidence_id": evidence.evidence_id,
            "disputed_evidence_ids": disputed_ids,
            "conflicted": has_conflict,
            "discovered_concepts": discovered_concepts,
            "new_rules": [self._rule_summary(rule) for rule in new_rules],
            "inferences": inferences,
            "integration_report_id": integration_report["integration_report_id"],
            "next_questions": self.propose_curiosity_questions(limit=4),
            "description": self.describe_concept(concept_name),
        }

    def invalidate_sample(self, sample_id: str, *, reason: str) -> dict[str, Any]:
        affected = self.evidence_ledger.invalidate_by_ref(sample_id, reason=reason)
        integration_report = self._integrate_cognition("evidence_invalidation")
        self._save_all_concepts()
        return {
            "sample_id": sample_id,
            "affected_evidence_ids": [item.evidence_id for item in affected],
            "reason": reason,
            "integration_report_id": integration_report["integration_report_id"],
        }

    def add_reference_claim(
        self,
        *,
        subject: str,
        predicate: str,
        object_value: str,
        statement: str,
        source_identity: str = "reference",
    ) -> dict[str, Any]:
        reference = self.evidence_ledger.add_evidence(
            claim=Claim(
                statement=statement,
                subject=subject,
                predicate=predicate,
                object=object_value,
            ),
            source_type="reference_evidence",
            source_identity=source_identity,
            refs=[source_identity],
            confidence=0.65,
            status="provisional",
        )
        disputed = []
        for existing in self.evidence_ledger.find_claims(subject=subject, predicate=predicate):
            if existing.evidence_id == reference.evidence_id:
                continue
            if existing.claim.object != object_value:
                updated = self.evidence_ledger.dispute(
                    existing.evidence_id,
                    reason=(
                        f"Reference claim {statement!r} conflicts with "
                        f"{existing.claim.statement!r}"
                    ),
                )
                if updated:
                    disputed.append(updated.evidence_id)

        if disputed:
            self.graph.add_open_question(
                subject,
                (
                    f"{subject} 的 {predicate} 关系存在冲突："
                    f"reference 说是 {object_value}，但已有证据给出不同说法。"
                ),
                "reference_conflicts_with_existing_evidence",
            )

        if predicate in {"is-a", "is-not-a", "contains", "supports", "made-of", "may_trigger", "can_affect", "related-to"}:
            self.graph.add_relation(
                subject,
                relation_type=predicate,
                target_name=object_value,
                confidence=0.6,
                evidence_refs=[reference.evidence_id],
            )
        else:
            self.graph.add_attribute(
                subject,
                attribute_name=predicate,
                value=object_value,
                confidence=0.55,
                evidence_refs=[reference.evidence_id],
                scope="reference",
                generalization_status="provisional_from_reference",
            )

        integration_report = self._integrate_cognition("reference_claim")
        self._save_all_concepts()
        return {
            "reference_evidence_id": reference.evidence_id,
            "disputed_evidence_ids": disputed,
            "integration_report_id": integration_report["integration_report_id"],
        }

    def _extract_relation(self, text: str) -> dict[str, str] | None:
        negative_match = re.search(r"(.+?)不是(?:一)?种(.+?)[。.!！]?$", text.strip())
        if negative_match:
            source = self._normalize_concept_name(negative_match.group(1))
            target = self._normalize_concept_name(negative_match.group(2))
            return {"source": source, "relation_type": "is-not-a", "target": target}

        match = re.search(r"(.+?)是(?:一)?种(.+?)[。.!！]?$", text.strip())
        if not match:
            return None
        source = self._normalize_concept_name(match.group(1))
        target = self._normalize_concept_name(match.group(2))
        return {"source": source, "relation_type": "is-a", "target": target}

    def _guess_concept(self, text: str) -> str:
        return self._normalize_concept_name(text.strip("。.!！?？"))

    def _normalize_concept_name(self, value: str) -> str:
        value = value.strip()
        aliases = {
            "苹果": "Apple",
            "桃子": "Peach",
            "梨": "Pear",
            "香蕉": "Banana",
            "番茄": "Tomato",
            "塑料苹果": "PlasticApple",
            "塑料水果": "PlasticFruit",
            "水果": "Fruit",
            "车辆": "Vehicle",
        }
        return aliases.get(value, value.title())

    def _build_description(self, source: str, target: str | None) -> str:
        if target:
            return (
                f"An early concept for {source}, formed from direct interaction, "
                f"perception evidence, and a candidate relation to {target}."
            )
        return f"An early concept for {source}, formed from direct interaction and perception evidence."

    def _load_existing_concepts(self) -> None:
        concepts = []
        for path in self.store.list_records("concepts"):
            try:
                import json

                with path.open("r", encoding="utf-8") as handle:
                    concepts.append(concept_from_dict(json.load(handle)))
            except (OSError, KeyError, ValueError, TypeError):
                continue
        self.graph.load(concepts)

    def _load_existing_rules(self) -> None:
        for path in self.store.list_records("rules"):
            try:
                import json

                with path.open("r", encoding="utf-8") as handle:
                    rule = rule_from_dict(json.load(handle))
                self.rules[rule.rule_id] = rule
            except (OSError, KeyError, ValueError, TypeError):
                continue

    def _integrate_cognition(self, trigger: str) -> dict[str, object]:
        report = self.cognitive_integration_engine.integrate(
            self.graph,
            evidence_statuses=self.evidence_ledger.status_map(),
            trigger=trigger,
        )
        self.store.save("reports", str(report["integration_report_id"]), report)
        return report

    def _save_all_concepts(self) -> None:
        for concept in self.graph.all_concepts():
            self.store.save("concepts", concept.concept_id, concept)

    def _rule_summary(self, rule: Rule) -> dict[str, Any]:
        return {
            "rule_id": rule.rule_id,
            "rule_type": rule.rule_type,
            "subject_concept": rule.subject_concept,
            "predicate": rule.predicate,
            "object_value": rule.object_value,
            "condition": rule.condition,
            "exceptions": rule.exceptions,
            "confidence": rule.confidence,
        }
