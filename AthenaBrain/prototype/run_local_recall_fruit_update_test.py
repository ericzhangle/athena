from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from athena_brain import CognitiveEngine
from athena_brain.llm_language_hub import LocalLLMConfig, LocalLanguageHub


class LocalRecallAnswerHub(LocalLanguageHub):
    def __init__(self) -> None:
        super().__init__(LocalLLMConfig(model="local-recall-answer-hub"))

    def parse_knowledge_text(self, *, text: str, known_concepts: list[str]) -> dict[str, Any]:
        raise RuntimeError("This test uses rule-based ingestion only.")

    def compose_grounded_answer(self, *, question: str, grounded_bundle: dict[str, Any]) -> dict[str, Any]:
        examples = grounded_bundle.get("examples", {}).get("Fruit", [])
        evidence_ids = [item["evidence_id"] for item in grounded_bundle.get("evidence", [])]
        event_ids = [item["event_id"] for item in grounded_bundle.get("events", [])]
        if question == "What examples does Fruit have?" and examples:
            return {
                "answer": "Based on my current memory, examples of Fruit include " + ", ".join(examples) + ".",
                "used_concepts": grounded_bundle.get("matched_concepts", []),
                "used_relations": [],
                "used_event_ids": event_ids,
                "used_evidence_ids": evidence_ids,
                "confidence": 0.8,
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
    data_root = root / "data" / "local_recall_fruit_update_test"
    if data_root.exists():
        shutil.rmtree(data_root)

    engine = CognitiveEngine(data_root, language_hub=LocalRecallAnswerHub())
    engine.ingest_knowledge_text(text="Apple is a Fruit. Grape is a Fruit. Fruit is a Food.", source_identity="setup")
    engine.ingest_knowledge_text(text="Car is a Vehicle.", source_identity="setup")
    pear_report = engine.ingest_knowledge_text(text="Pear is a Fruit.", source_identity="fruit_update")

    working_memory_names = sorted(concept.name for concept in engine.graph.all_concepts())
    fruit_answer = engine.answer_grounded_question(question="What examples does Fruit have?")
    fruit_examples = fruit_answer["grounded_bundle"]["examples"].get("Fruit", [])

    validation_observations = [
        f"Recall anchors during Pear update: {pear_report['recall']['anchor_names']}",
        f"Working memory after Pear update: {working_memory_names}",
        f"Fruit examples after local recall: {fruit_examples}",
        f"Fruit answer: {fruit_answer['answer']}",
    ]

    remaining_issues = []
    if "Pear" not in working_memory_names:
        remaining_issues.append("Pear was not present in working memory after the local fruit update.")
    if "Fruit" not in working_memory_names:
        remaining_issues.append("Fruit anchor neighborhood was not recalled into working memory.")
    if "Apple" not in working_memory_names or "Grape" not in working_memory_names:
        remaining_issues.append("Fruit neighborhood did not bring back existing fruit examples.")
    if "Car" in working_memory_names:
        remaining_issues.append("Unrelated vehicle concepts leaked into the fruit working memory.")
    if "Pear" not in fruit_examples:
        remaining_issues.append("Fruit examples did not include Pear after the local update.")

    full_report = {
        "data_root": str(data_root),
        "pear_ingestion_report": pear_report,
        "working_memory_names": working_memory_names,
        "fruit_answer": fruit_answer,
        "validation_observations": validation_observations,
        "remaining_issues": remaining_issues,
    }
    report_path = data_root / "local_recall_fruit_update_report.json"
    report_path.write_text(json.dumps(full_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Local recall fruit update test finished.")
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
        print("- No blocking issue found in local fruit recall + update flow.")


if __name__ == "__main__":
    main()
