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
from .llm_language_hub import LocalLLMUnavailableError, LocalLanguageHub
from .memory_index import MemoryIndex
from .memory_retriever import MemoryRetriever
from .models import Claim, CognitiveEvent, Experience, Rule, concept_from_dict, new_id, rule_from_dict
from .perception import PerceptionInterface
from .reasoning_engine import ReasoningEngine
from .sleep_engine import SleepEngine
from .state_manager import StateManager
from .store import JsonMemoryStore


class CognitiveEngine:
    """Coordinates the first BabyBrain learning loop."""

    def __init__(
        self,
        data_root: str | Path,
        *,
        language_hub: LocalLanguageHub | None = None,
    ) -> None:
        self.store = JsonMemoryStore(data_root)
        self.memory_index = MemoryIndex(self.store)
        self.evidence_ledger = EvidenceLedger(self.store, autoload=False)
        self.state_manager = StateManager()
        self.perception_interface = PerceptionInterface()
        self.attribute_normalizer = AttributeNormalizer()
        self.curiosity_engine = CuriosityEngine()
        self.knowledge_ingestion_engine = KnowledgeIngestionEngine()
        self.language_hub = language_hub or LocalLanguageHub()
        self.memory_retriever = MemoryRetriever()
        self.inquiry_loop_engine = InquiryLoopEngine()
        self.cognitive_integration_engine = CognitiveIntegrationEngine()
        self.reasoning_engine = ReasoningEngine()
        self.rules: dict[str, Rule] = {}
        self.graph = ConceptGraph()
        self.working_memory_state = self._empty_working_memory_state()
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
        self.working_memory_state = self._build_working_memory_state(
            anchor_names=[source_concept] + ([target_concept] if target_concept else []),
            source="guided_example_learning",
        )
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
        self.recall_concepts_into_working_memory([concept_name], hops=2)
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

    def clear_working_memory(self) -> None:
        self.graph = ConceptGraph()
        self.evidence_ledger.clear()
        self.working_memory_state = self._empty_working_memory_state()

    def load_working_set(
        self,
        *,
        concepts,
        evidence_ids: list[str],
        anchor_names: list[str] | None = None,
        source: str = "manual_load",
    ) -> None:
        self.clear_working_memory()
        self.graph.load(list(concepts))
        self.evidence_ledger.load_evidence_ids(evidence_ids)
        self.working_memory_state = self._build_working_memory_state(
            anchor_names=anchor_names or [],
            source=source,
        )

    def recall_concepts_into_working_memory(
        self,
        anchor_names: list[str],
        *,
        hops: int = 1,
    ) -> dict[str, Any]:
        normalized = []
        seen = set()
        for name in anchor_names:
            canonical = self._normalize_concept_name(name)
            if not canonical or canonical in seen:
                continue
            normalized.append(canonical)
            seen.add(canonical)
        neighborhood = self.memory_retriever.retrieve_neighborhood(
            anchor_names=normalized,
            memory_index=self.memory_index,
            hops=hops,
        )
        self.load_working_set(
            concepts=neighborhood["concepts"],
            evidence_ids=neighborhood["evidence_ids"],
            anchor_names=normalized,
            source="concept_recall",
        )
        return {
            "anchor_names": neighborhood["anchor_names"],
            "anchor_ids": neighborhood["anchor_ids"],
            "concept_ids": neighborhood["concept_ids"],
            "loaded_concepts": [concept.name for concept in neighborhood["concepts"]],
            "evidence_ids": neighborhood["evidence_ids"],
            "active_concepts": list(self.working_memory_state["active_concepts"]),
            "working_memory_source": self.working_memory_state["source"],
        }

    def list_known_concepts(self) -> list[dict[str, Any]]:
        return [
            {
                "name": record.name,
                "maturity": record.maturity,
                "confidence": record.confidence,
                "description": record.description,
            }
            for record in self.memory_index.list_concept_records()
        ]

    def working_memory_summary(self) -> dict[str, Any]:
        return dict(self.working_memory_state)

    def propose_curiosity_questions(self, *, limit: int = 6) -> list[dict[str, object]]:
        if not self.graph.all_concepts():
            return []
        focus_concepts = list(self.working_memory_state.get("active_concepts", []))
        return self.curiosity_engine.propose_questions(
            self.graph,
            limit=limit,
            focus_concepts=focus_concepts or None,
        )

    def run_inquiry_loop(self, *, max_steps: int = 10) -> dict[str, object]:
        report = self.inquiry_loop_engine.run(self, max_steps=max_steps)
        self.store.save("reports", str(report["inquiry_report_id"]), report)
        return report

    def ingest_knowledge_with_llm(
        self,
        *,
        text: str,
        source_identity: str = "user_knowledge_text_llm",
    ) -> dict[str, Any]:
        known_concepts = [record.name for record in self.memory_index.list_concept_records()]
        llm_result = self.language_hub.parse_knowledge_text(
            text=text,
            known_concepts=known_concepts,
        )
        claims, validation = self._claims_from_llm_parse(llm_result, text=text)
        report = self._ingest_claims(
            text=text,
            claims=claims,
            source_identity=source_identity,
            source_type="llm_knowledge_text",
            tags=["knowledge_ingestion", "article_text", "llm_language_hub"],
            trigger="knowledge_ingestion_llm",
        )
        report["llm_parse"] = llm_result
        report["llm_validation"] = validation
        return report

    def ingest_knowledge_text(
        self,
        *,
        text: str,
        source_identity: str = "user_knowledge_text",
    ) -> dict[str, Any]:
        claims = self.knowledge_ingestion_engine.extract_claims(text)
        return self._ingest_claims(
            text=text,
            claims=claims,
            source_identity=source_identity,
            source_type="user_knowledge_text",
            tags=["knowledge_ingestion", "article_text"],
            trigger="knowledge_ingestion",
        )

    def answer_grounded_question(self, *, question: str) -> dict[str, Any]:
        recall_report = self.recall_concepts_into_working_memory(
            self._anchor_names_from_question(question),
            hops=2,
        )
        bundle = self.memory_retriever.retrieve(
            question=question,
            graph=self.graph,
            store=self.store,
            evidence_ledger=self.evidence_ledger,
        )
        if not self._grounded_bundle_has_direct_support(bundle):
            return self._deterministic_unknown_grounded_answer(
                question=question,
                bundle=bundle,
                reason="no_direct_grounded_support",
                recall=recall_report,
            )
        try:
            llm_result = self.language_hub.compose_grounded_answer(
                question=question,
                grounded_bundle=bundle,
            )
        except LocalLLMUnavailableError as exc:
            return {
                "question": question,
                "answer": (
                    "本地 LLM 语言中枢当前不可用，因此不能生成 grounded answer。"
                    f" 原因: {exc}"
                ),
                "grounded_bundle": bundle,
                "llm_available": False,
                "source": "memory_graph_only",
                "recall": recall_report,
            }
        llm_result = self._validated_grounded_llm_result(bundle=bundle, llm_result=llm_result)

        event = self._record_event(
            event_type="grounded_question_answered",
            summary=f"Answered grounded question: {question}",
            source="local_llm_language_hub",
            payload={
                "question": question,
                "grounded_bundle": bundle,
                "llm_result": llm_result,
            },
        )
        return {
            "question": question,
            "answer": llm_result.get("answer", ""),
            "grounded_bundle": bundle,
            "used_concepts": llm_result.get("used_concepts", []),
            "used_relations": llm_result.get("used_relations", []),
            "used_event_ids": llm_result.get("used_event_ids", []),
            "used_evidence_ids": llm_result.get("used_evidence_ids", []),
            "confidence": llm_result.get("confidence", 0.0),
            "insufficient_memory": llm_result.get("insufficient_memory", False),
            "llm_available": True,
            "event_id": event.event_id,
            "source": "grounded_local_llm",
            "recall": recall_report,
        }

    def _grounded_bundle_has_direct_support(self, bundle: dict[str, Any]) -> bool:
        matched_concepts = list(bundle.get("matched_concepts", []))
        relations = [tuple(item) for item in bundle.get("relations", []) if len(item) == 3]
        examples = dict(bundle.get("examples", {}))
        concepts = list(bundle.get("concepts", []))
        question_type = str(bundle.get("question_type", "open_question"))
        requested_attribute = bundle.get("requested_attribute")

        if bundle.get("unknown"):
            return False
        if question_type == "describe":
            return bool(matched_concepts)
        if question_type == "belongs_to":
            return any(relation_type == "is-a" for _, relation_type, _ in relations)
        if question_type == "examples_of":
            return any(value for value in examples.values())
        if question_type == "is_a":
            if len(matched_concepts) < 2:
                return False
            return any(
                subject == matched_concepts[0] and relation_type == "is-a" and target == matched_concepts[1]
                for subject, relation_type, target in relations
            )
        if requested_attribute:
            for concept in concepts:
                for attribute in concept.get("attributes", []):
                    if str(attribute.get("name")) == requested_attribute:
                        return True
            return False
        return bool(relations or examples or concepts)

    def _validated_grounded_llm_result(
        self,
        *,
        bundle: dict[str, Any],
        llm_result: dict[str, Any],
    ) -> dict[str, Any]:
        allowed_event_ids = {item["event_id"] for item in bundle.get("events", []) if item.get("event_id")}
        allowed_evidence_ids = {item["evidence_id"] for item in bundle.get("evidence", []) if item.get("evidence_id")}
        allowed_relations = {
            tuple(item)
            for item in bundle.get("relations", [])
            if isinstance(item, list) and len(item) == 3
        }

        used_event_ids = [item for item in llm_result.get("used_event_ids", []) if item in allowed_event_ids]
        used_evidence_ids = [item for item in llm_result.get("used_evidence_ids", []) if item in allowed_evidence_ids]
        used_relations = [
            item
            for item in llm_result.get("used_relations", [])
            if isinstance(item, list) and tuple(item) in allowed_relations
        ]
        validated = dict(llm_result)
        validated["used_event_ids"] = used_event_ids
        validated["used_evidence_ids"] = used_evidence_ids
        validated["used_relations"] = used_relations

        if (
            not validated.get("insufficient_memory", False)
            and not (used_event_ids or used_evidence_ids or used_relations)
            and bundle.get("question_type") != "describe"
        ):
            return {
                "answer": "我现在还不能从自己的记忆里直接支持这个答案，所以只能说暂时不知道。",
                "used_concepts": bundle.get("matched_concepts", []),
                "used_relations": [],
                "used_event_ids": [],
                "used_evidence_ids": [],
                "confidence": 0.0,
                "insufficient_memory": True,
            }
        return validated

    def _deterministic_unknown_grounded_answer(
        self,
        *,
        question: str,
        bundle: dict[str, Any],
        reason: str,
        recall: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "question": question,
            "answer": "我现在不知道，因为我的记忆里还没有足够直接的依据来回答这个问题。",
            "grounded_bundle": bundle,
            "used_concepts": bundle.get("matched_concepts", []),
            "used_relations": [],
            "used_event_ids": [],
            "used_evidence_ids": [],
            "confidence": 0.0,
            "insufficient_memory": True,
            "llm_available": self.language_hub.is_available(),
            "source": reason,
            "recall": recall or {},
        }

    def answer_curiosity_question(
        self,
        *,
        concept_name: str,
        question: str,
        answer: str,
        source_identity: str = "user",
    ) -> dict[str, Any]:
        concept_name = self._normalize_concept_name(concept_name)
        recall_report = self.recall_concepts_into_working_memory([concept_name], hops=2)
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
        result = {
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
            "recall": recall_report,
        }
        event = self._record_event(
            event_type="curiosity_answered",
            summary=f"Answered curiosity question about {concept_name}.",
            source=source_identity,
            payload={
                "concept": concept_name,
                "question_id": question_id,
                "question": question,
                "answer": answer,
                "answer_evidence_id": evidence.evidence_id,
                "conflicted": has_conflict,
                "discovered_concepts": discovered_concepts,
                "new_rules": result["new_rules"],
                "inferences": inferences,
                "integration_report_id": integration_report["integration_report_id"],
            },
        )
        result["event_id"] = event.event_id
        return result

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

    def _empty_working_memory_state(self) -> dict[str, Any]:
        return {
            "anchor_names": [],
            "active_concepts": [],
            "loaded_concepts": [],
            "source": "empty",
        }

    def _build_working_memory_state(
        self,
        *,
        anchor_names: list[str],
        source: str,
    ) -> dict[str, Any]:
        available = {concept.name for concept in self.graph.all_concepts()}
        active = {name for name in anchor_names if name}

        for anchor_name in list(active):
            if anchor_name not in available:
                continue
            anchor = self.graph.get_or_create(anchor_name)
            for relation in anchor.relations:
                if relation.target_concept in available:
                    active.add(relation.target_concept)
            for item in anchor.examples + anchor.counterexamples:
                candidate = str(item.get("concept", "")).strip()
                if candidate and candidate in available:
                    active.add(candidate)

        for concept in self.graph.all_concepts():
            if concept.name in active:
                continue
            if any(relation.target_concept in active for relation in concept.relations):
                active.add(concept.name)

        return {
            "anchor_names": list(anchor_names),
            "active_concepts": sorted(active),
            "loaded_concepts": sorted(available),
            "source": source,
        }

    def _anchor_names_from_claims(self, claims: list[dict[str, Any]], *, text: str) -> list[str]:
        anchors = []
        seen = set()
        for claim in claims:
            for key in ["subject", "target"]:
                value = str(claim.get(key, "")).strip()
                if not value:
                    continue
                canonical = self._normalize_concept_name(value)
                if canonical in seen:
                    continue
                anchors.append(canonical)
                seen.add(canonical)
        for value in self.memory_index.concept_names_in_text(text):
            canonical = self._normalize_concept_name(value)
            if canonical in seen:
                continue
            anchors.append(canonical)
            seen.add(canonical)
        return anchors

    def _anchor_names_from_question(self, question: str) -> list[str]:
        anchors = []
        seen = set()
        for value in self.memory_index.concept_names_in_text(question):
            canonical = self._normalize_concept_name(value)
            if canonical in seen:
                continue
            anchors.append(canonical)
            seen.add(canonical)
        return anchors

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

    def _claims_from_llm_parse(
        self,
        payload: dict[str, Any],
        *,
        text: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        claims: list[dict[str, Any]] = []
        validation = {
            "dropped_relations": [],
            "dropped_attributes": [],
            "dropped_concepts": [],
            "converted_relations_to_attributes": [],
        }
        concepts_payload = payload.get("concepts", [])
        discovered_concepts = {
            str(concept.get("name", "")).strip()
            for concept in concepts_payload
            if str(concept.get("name", "")).strip()
        }
        for relation in payload.get("relations", []):
            subject = str(relation.get("subject", "")).strip()
            relation_type = self._normalize_llm_relation_type(str(relation.get("relation_type", "")).strip())
            target = str(relation.get("target", "")).strip()
            statement = str(relation.get("statement", "")).strip() or f"{subject} {relation_type} {target}"
            if not (subject and relation_type and target):
                validation["dropped_relations"].append({"relation": relation, "reason": "missing_field"})
                continue
            if self._is_invalid_llm_concept_name(subject) or self._is_invalid_llm_concept_name(target):
                validation["dropped_relations"].append({"relation": relation, "reason": "invalid_concept_name"})
                continue
            attribute_from_relation = self._attribute_claim_from_llm_relation(
                subject=subject,
                relation_type=relation_type,
                target=target,
                statement=statement,
            )
            if attribute_from_relation is not None:
                claims.append(attribute_from_relation)
                validation["converted_relations_to_attributes"].append(
                    {
                        "relation": relation,
                        "attribute": attribute_from_relation,
                    }
                )
                continue
            if relation_type not in {
                "is-a",
                "is-not-a",
                "contains",
                "supports",
                "made-of",
                "related-to",
                "can_affect",
                "may_trigger",
                "can-be-made-into",
            }:
                validation["dropped_relations"].append({"relation": relation, "reason": "unsupported_relation_type"})
                continue
            if discovered_concepts and subject not in discovered_concepts:
                discovered_concepts.add(subject)
            if discovered_concepts and target not in discovered_concepts and not self._appears_in_text(target, text):
                validation["dropped_relations"].append({"relation": relation, "reason": "target_not_grounded_in_text"})
                continue
            claims.append(
                {
                    "kind": "relation",
                    "subject": subject,
                    "predicate": relation_type,
                    "object": target,
                    "relation_type": relation_type,
                    "target": target,
                    "statement": statement,
                    "questions": [],
                }
            )
        for attribute in payload.get("attributes", []):
            subject = str(attribute.get("subject", "")).strip()
            attribute_name = str(attribute.get("attribute_name", "")).strip()
            attribute_value = str(attribute.get("attribute_value", "")).strip()
            statement = str(attribute.get("statement", "")).strip() or attribute_value
            if not (subject and attribute_name and attribute_value):
                validation["dropped_attributes"].append({"attribute": attribute, "reason": "missing_field"})
                continue
            if self._is_invalid_llm_concept_name(subject):
                validation["dropped_attributes"].append({"attribute": attribute, "reason": "invalid_subject"})
                continue
            if subject not in discovered_concepts and not self._appears_in_text(subject, text):
                validation["dropped_attributes"].append({"attribute": attribute, "reason": "subject_not_grounded_in_text"})
                continue
            claims.append(
                {
                    "kind": "attribute",
                    "subject": subject,
                    "predicate": attribute_name,
                    "object": attribute_value,
                    "attribute_name": attribute_name,
                    "attribute_value": attribute_value,
                    "statement": statement,
                    "questions": [],
                }
            )
        for concept in concepts_payload:
            name = str(concept.get("name", "")).strip()
            surface = str(concept.get("surface", name)).strip()
            if not name:
                continue
            if self._is_invalid_llm_concept_name(name):
                validation["dropped_concepts"].append({"concept": concept, "reason": "invalid_name"})
                continue
            if not self._appears_in_text(surface or name, text):
                validation["dropped_concepts"].append({"concept": concept, "reason": "not_grounded_in_text"})
                continue
            claims.append(
                {
                    "kind": "concept",
                    "subject": name,
                    "predicate": "mentioned_in_llm_parse",
                    "object": "mentioned",
                    "statement": surface or name,
                    "questions": [],
                }
            )
        suggested_questions = payload.get("suggested_questions", [])
        if suggested_questions:
            by_subject: dict[str, list[dict[str, str]]] = {}
            for item in suggested_questions:
                concept = str(item.get("concept", "")).strip()
                question = str(item.get("question", "")).strip()
                reason = str(item.get("reason", "llm_suggested_question")).strip() or "llm_suggested_question"
                if not (concept and question):
                    continue
                if self._is_invalid_llm_concept_name(concept):
                    continue
                if concept not in discovered_concepts and not self._appears_in_text(concept, text):
                    continue
                by_subject.setdefault(concept, []).append({"question": question, "reason": reason})
            for claim in claims:
                claim["questions"] = by_subject.get(str(claim["subject"]), [])
        return self._dedupe_llm_claims(claims), validation

    def _normalize_llm_relation_type(self, relation_type: str) -> str:
        normalized = relation_type.strip().replace("_", "-").lower()
        aliases = {
            "isa": "is-a",
            "is a": "is-a",
            "is-not": "is-not-a",
            "is not a": "is-not-a",
            "related to": "related-to",
            "can affect": "can_affect",
            "may trigger": "may_trigger",
            "made of": "made-of",
        }
        return aliases.get(normalized, normalized)

    def _is_invalid_llm_concept_name(self, name: str) -> bool:
        stripped = name.strip()
        if not stripped:
            return True
        placeholders = {
            "ConceptName",
            "Entity",
            "Object",
            "Unknown",
            "Example",
            "Category",
        }
        if stripped in placeholders:
            return True
        if stripped.lower() in {"conceptname", "entity", "object", "unknown", "example", "category"}:
            return True
        return False

    def _appears_in_text(self, value: str, text: str) -> bool:
        candidate = value.strip()
        if not candidate:
            return False
        return candidate.casefold() in text.casefold()

    def _attribute_claim_from_llm_relation(
        self,
        *,
        subject: str,
        relation_type: str,
        target: str,
        statement: str,
    ) -> dict[str, Any] | None:
        lowered_target = target.strip().casefold()
        lowered_statement = statement.casefold()
        if relation_type == "is-a" and lowered_target in {"edible", "inedible", "not edible"}:
            value = "edible" if lowered_target == "edible" else "not edible"
            return {
                "kind": "attribute",
                "subject": subject,
                "predicate": "edibility",
                "object": value,
                "attribute_name": "edibility",
                "attribute_value": value,
                "statement": statement,
                "questions": [],
            }
        if relation_type == "is-a" and " is edible" in lowered_statement:
            return {
                "kind": "attribute",
                "subject": subject,
                "predicate": "edibility",
                "object": "edible",
                "attribute_name": "edibility",
                "attribute_value": "edible",
                "statement": statement,
                "questions": [],
            }
        return None

    def _dedupe_llm_claims(self, claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for claim in claims:
            key = (
                str(claim.get("kind", "")),
                str(claim.get("subject", "")),
                str(claim.get("predicate", "")),
                str(claim.get("object", "")),
            )
            existing = seen.get(key)
            if existing is None:
                claim["questions"] = list(claim.get("questions", []))
                seen[key] = claim
                deduped.append(claim)
                continue
            existing_questions = {
                (str(item.get("question", "")), str(item.get("reason", "")))
                for item in existing.get("questions", [])
            }
            for item in claim.get("questions", []):
                pair = (str(item.get("question", "")), str(item.get("reason", "")))
                if pair in existing_questions:
                    continue
                existing.setdefault("questions", []).append(item)
                existing_questions.add(pair)
        return deduped

    def _ingest_claims(
        self,
        *,
        text: str,
        claims: list[dict[str, Any]],
        source_identity: str,
        source_type: str,
        tags: list[str],
        trigger: str,
    ) -> dict[str, Any]:
        recall_report = self.recall_concepts_into_working_memory(
            self._anchor_names_from_claims(claims, text=text),
            hops=2,
        )
        text_ref = new_id("knowledge_text")
        experience = Experience(
            raw_inputs=[{"type": "text", "speaker": "user", "content": text, "ref": text_ref}],
            perception_refs=[],
            athena_questions=[],
            user_feedback=[],
            tags=tags,
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
                source_type=source_type,
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

        integration_report = self._integrate_cognition(trigger)
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
            "recall": recall_report,
        }
        event = self._record_event(
            event_type="knowledge_ingested",
            summary=f"Ingested knowledge text with {len(claims)} extracted claims.",
            source=source_identity,
            payload={
                "input_text": text,
                "experience_id": experience.experience_id,
                "report_id": report["report_id"],
                "claim_count": len(claims),
                "evidence_ids": evidence_ids,
                "updated_concepts": sorted(updated_concepts),
                "generated_questions": report["generated_questions"],
                "integration_report_id": integration_report["integration_report_id"],
            },
        )
        report["event_id"] = event.event_id
        self.store.save("reports", report["report_id"], report)
        return report

    def _integrate_cognition(self, trigger: str) -> dict[str, object]:
        report = self.cognitive_integration_engine.integrate(
            self.graph,
            evidence_statuses=self.evidence_ledger.status_map(),
            trigger=trigger,
        )
        self.store.save("reports", str(report["integration_report_id"]), report)
        return report

    def _record_event(
        self,
        *,
        event_type: str,
        summary: str,
        source: str,
        payload: dict[str, Any],
    ) -> CognitiveEvent:
        event = CognitiveEvent(
            event_type=event_type,
            summary=summary,
            source=source,
            payload=payload,
        )
        self.store.save("events", event.event_id, event)
        return event

    def _save_all_concepts(self) -> None:
        for concept in self.graph.all_concepts():
            self.store.save("concepts", concept.concept_id, concept)
        self.memory_index.refresh()

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
