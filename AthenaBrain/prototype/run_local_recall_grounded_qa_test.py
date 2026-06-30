from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from athena_brain import CognitiveEngine
from athena_brain.llm_language_hub import LocalLLMConfig, LocalLanguageHub


class TrackingGroundedRecallHub(LocalLanguageHub):
    def __init__(self) -> None:
        super().__init__(LocalLLMConfig(model="tracking-grounded-recall-hub"))
        self.answer_calls: list[str] = []

    def parse_knowledge_text(self, *, text: str, known_concepts: list[str]) -> dict[str, Any]:
        raise RuntimeError("This test uses rule-based ingestion only.")

    def compose_grounded_answer(self, *, question: str, grounded_bundle: dict[str, Any]) -> dict[str, Any]:
        self.answer_calls.append(question)
        relations = {tuple(item) for item in grounded_bundle.get("relations", []) if len(item) == 3}
        evidence_ids = [item["evidence_id"] for item in grounded_bundle.get("evidence", [])]
        event_ids = [item["event_id"] for item in grounded_bundle.get("events", [])]

        if question == "Apple belongs to what?" and ("Apple", "is-a", "Fruit") in relations:
            return {
                "answer": "Based on my current memory, Apple belongs to Fruit.",
                "used_concepts": grounded_bundle.get("matched_concepts", []),
                "used_relations": [["Apple", "is-a", "Fruit"]],
                "used_event_ids": event_ids,
                "used_evidence_ids": evidence_ids,
                "confidence": 0.82,
                "insufficient_memory": False,
            }
        return {
            "answer": "I do not know yet based on my current memory.",
            "used_concepts": grounded_bundle.get("matched_concepts", []),
            "used_relations": [],
            "used_event_ids": event_ids,
            "used_evidence_ids": evidence_ids,
            "confidence": 0.2,
            "insufficient_memory": True,
        }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    root = Path(__file__).resolve().parent
    data_root = root / "data" / "local_recall_grounded_qa_test"
    if data_root.exists():
        shutil.rmtree(data_root)

    setup_engine = CognitiveEngine(data_root, language_hub=TrackingGroundedRecallHub())
    setup_engine.ingest_knowledge_text(text="Apple is a Fruit. Grape is a Fruit. Fruit is a Food.", source_identity="setup")
    setup_engine.ingest_knowledge_text(text="Car is a Vehicle.", source_identity="setup")

    hub = TrackingGroundedRecallHub()
    engine = CognitiveEngine(data_root, language_hub=hub)
    apple_answer = engine.answer_grounded_question(question="Apple belongs to what?")
    apple_working_memory = sorted(concept.name for concept in engine.graph.all_concepts())
    missile_answer = engine.answer_grounded_question(question="导弹是什么？")
    missile_working_memory = sorted(concept.name for concept in engine.graph.all_concepts())

    validation_observations = [
        f"Apple recall anchors: {apple_answer.get('recall', {}).get('anchor_names', [])}",
        f"Apple working memory: {apple_working_memory}",
        f"Missile recall anchors: {missile_answer.get('recall', {}).get('anchor_names', [])}",
        f"Missile working memory: {missile_working_memory}",
        f"Language hub calls: {hub.answer_calls}",
    ]

    remaining_issues = []
    if apple_answer["source"] != "grounded_local_llm":
        remaining_issues.append("Supported fruit question did not use the grounded local language hub.")
    if "Car" in apple_working_memory:
        remaining_issues.append("Unrelated vehicle concept leaked into the fruit QA working memory.")
    if missile_answer["source"] != "no_direct_grounded_support":
        remaining_issues.append("Unknown missile question did not stop at the grounded guard.")
    if "导弹是什么？" in hub.answer_calls:
        remaining_issues.append("Language hub was still called for the unknown missile question.")
    if missile_working_memory:
        remaining_issues.append("Unknown missile question should not have recalled any concept neighborhood.")

    full_report = {
        "data_root": str(data_root),
        "apple_answer": apple_answer,
        "apple_working_memory": apple_working_memory,
        "missile_answer": missile_answer,
        "missile_working_memory": missile_working_memory,
        "llm_answer_calls": hub.answer_calls,
        "validation_observations": validation_observations,
        "remaining_issues": remaining_issues,
    }
    report_path = data_root / "local_recall_grounded_qa_report.json"
    report_path.write_text(json.dumps(full_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Local recall grounded QA test finished.")
    print(f"Records saved to: {data_root}")
    print()
    print("Validation observations:")
    for item in validation_observations:
        print(f"- {item}")
    print()
    print("Remaining issues:")
    if remaining_issues:
        for item in remaining_issues:
            print(f"- {item}")
    else:
        print("- No blocking issue found in local recall grounded QA flow.")


if __name__ == "__main__":
    main()
