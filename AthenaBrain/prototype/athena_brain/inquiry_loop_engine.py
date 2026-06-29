from __future__ import annotations

from .inquiry_provider import MockInquiryProvider
from .models import new_id, now_iso


class InquiryLoopEngine:
    """Runs a bounded curiosity -> reference -> ingestion loop."""

    def __init__(self, provider: MockInquiryProvider | None = None) -> None:
        self.provider = provider or MockInquiryProvider()

    def run(self, cognitive_engine, *, max_steps: int = 10) -> dict[str, object]:
        steps = []
        seen_questions = set()
        for step_index in range(max_steps):
            question = self._select_question(cognitive_engine, seen_questions)
            if question is None:
                break
            seen_questions.add(question["question"])

            provider_result = self.provider.answer(str(question["question"]))
            ingestion_report = cognitive_engine.ingest_knowledge_text(
                text=provider_result["answer"],
                source_identity=provider_result["provider"],
            )
            cognitive_engine.graph.record_question_answer(
                str(question["concept"]),
                question=str(question["question"]),
                answer=provider_result["answer"],
                evidence_id=str(ingestion_report["experience_id"]),
            )
            concept = cognitive_engine.graph.get_or_create(str(question["concept"]))
            for item in concept.open_questions:
                if item.get("question") == question["question"]:
                    item["status"] = "answered_by_reference"
                    break
            concept.touch()
            cognitive_engine._save_all_concepts()
            steps.append(
                {
                    "step": step_index + 1,
                    "question": question,
                    "provider": provider_result["provider"],
                    "answer": provider_result["answer"],
                    "claim_count": ingestion_report["claim_count"],
                    "updated_concepts": ingestion_report["updated_concepts"],
                    "new_top_questions": ingestion_report["generated_questions"][:5],
                }
            )

        return {
            "inquiry_report_id": new_id("inquiry_report"),
            "timestamp": now_iso(),
            "provider": self.provider.__class__.__name__,
            "requested_steps": max_steps,
            "completed_steps": len(steps),
            "steps": steps,
            "final_top_questions": cognitive_engine.propose_curiosity_questions(limit=12),
        }

    def _select_question(self, cognitive_engine, seen_questions: set[str]) -> dict[str, object] | None:
        for question in cognitive_engine.propose_curiosity_questions(limit=40):
            if question["question"] in seen_questions:
                continue
            return question
        return None
