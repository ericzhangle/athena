from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from athena_brain import CognitiveEngine
from athena_brain.llm_language_hub import LocalLLMConfig, LocalLanguageHub


class LeakyTestHub(LocalLanguageHub):
    """A deliberately unsafe test hub used to verify engine-side guards."""

    def __init__(self) -> None:
        super().__init__(LocalLLMConfig(model="leaky-test-hub"))
        self.answer_calls: list[str] = []

    def parse_knowledge_text(self, *, text: str, known_concepts: list[str]) -> dict[str, Any]:
        return {
            "concepts": [
                {"name": "Apple", "surface": "Apple"},
                {"name": "Fruit", "surface": "Fruit"},
                {"name": "Cookie", "surface": "Cookie"},
                {"name": "Food", "surface": "Food"},
            ],
            "relations": [
                {"subject": "Apple", "relation_type": "is-a", "target": "Fruit", "statement": "Apple is a Fruit."},
                {"subject": "Cookie", "relation_type": "is-a", "target": "Food", "statement": "Cookie is a Food."},
            ],
            "attributes": [],
            "suggested_questions": [],
            "uncertainties": [],
        }

    def compose_grounded_answer(self, *, question: str, grounded_bundle: dict[str, Any]) -> dict[str, Any]:
        self.answer_calls.append(question)
        if "导弹" in question or "missile" in question.casefold():
            return {
                "answer": "导弹是一种武器。",
                "used_concepts": [],
                "used_relations": [],
                "used_event_ids": [],
                "used_evidence_ids": [],
                "confidence": 0.99,
                "insufficient_memory": False,
            }
        if "color" in question.casefold():
            return {
                "answer": "Cookie is brown.",
                "used_concepts": ["Cookie"],
                "used_relations": [],
                "used_event_ids": [],
                "used_evidence_ids": [],
                "confidence": 0.99,
                "insufficient_memory": False,
            }
        return {
            "answer": "Apple belongs to Fruit.",
            "used_concepts": ["Apple", "Fruit"],
            "used_relations": [["Apple", "is-a", "Fruit"]],
            "used_event_ids": [],
            "used_evidence_ids": [],
            "confidence": 0.8,
            "insufficient_memory": False,
        }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    root = Path(__file__).resolve().parent
    data_root = root / "data" / "grounded_leakage_test"
    if data_root.exists():
        shutil.rmtree(data_root)

    hub = LeakyTestHub()
    engine = CognitiveEngine(data_root, language_hub=hub)
    engine.ingest_knowledge_with_llm(
        text="Apple is a Fruit. Cookie is a Food.",
        source_identity="grounded_leakage_test_setup",
    )

    missile_answer = engine.answer_grounded_question(question="导弹是什么？")
    cookie_color_answer = engine.answer_grounded_question(question="What color is Cookie?")
    apple_answer = engine.answer_grounded_question(question="Apple belongs to what?")

    validation_observations = [
        f"Missile answer: {missile_answer['answer']}",
        f"Cookie color answer: {cookie_color_answer['answer']}",
        f"Apple answer: {apple_answer['answer']}",
        f"LLM compose calls: {hub.answer_calls}",
    ]

    remaining_issues = []
    if missile_answer["source"] != "no_direct_grounded_support":
        remaining_issues.append("Unknown concept question did not short-circuit before LLM answering.")
    if "导弹是一种武器" in missile_answer["answer"]:
        remaining_issues.append("Engine leaked model-side world knowledge for missile question.")
    if cookie_color_answer["source"] != "no_direct_grounded_support":
        remaining_issues.append("Unsupported attribute question did not short-circuit before LLM answering.")
    if "brown" in cookie_color_answer["answer"].lower():
        remaining_issues.append("Engine leaked model-side world knowledge for Cookie color.")
    if apple_answer["source"] != "grounded_local_llm":
        remaining_issues.append("Supported grounded question did not use the language hub.")
    if "导弹是什么？" in hub.answer_calls:
        remaining_issues.append("Language hub was still called for an unknown missile question.")
    if "What color is Cookie?" in hub.answer_calls:
        remaining_issues.append("Language hub was still called for an unsupported Cookie color question.")
    if "Apple belongs to what?" not in hub.answer_calls:
        remaining_issues.append("Language hub was not called for a supported grounded question.")

    full_report = {
        "data_root": str(data_root),
        "missile_answer": missile_answer,
        "cookie_color_answer": cookie_color_answer,
        "apple_answer": apple_answer,
        "llm_answer_calls": hub.answer_calls,
        "validation_observations": validation_observations,
        "remaining_issues": remaining_issues,
    }
    report_path = data_root / "grounded_leakage_report.json"
    report_path.write_text(json.dumps(full_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Grounded leakage guard test finished.")
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
        print("- No leakage issue found in engine-side grounded guards.")


if __name__ == "__main__":
    main()
