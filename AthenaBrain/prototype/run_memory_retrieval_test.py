from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from athena_brain import CognitiveEngine
from athena_brain.llm_language_hub import LocalLLMConfig, LocalLanguageHub


LESSON_TEXT = (
    "Apple is a Fruit. "
    "Grape is a Fruit. "
    "Cookie is a Food. "
    "Fruit is a Food. "
    "Food is edible."
)


class GroundedAnswerTestHub(LocalLanguageHub):
    def __init__(self) -> None:
        super().__init__(LocalLLMConfig(model="grounded-answer-test-hub"))

    def parse_knowledge_text(self, *, text: str, known_concepts: list[str]) -> dict[str, Any]:
        return {
            "concepts": [
                {"name": "Apple", "surface": "Apple"},
                {"name": "Grape", "surface": "Grape"},
                {"name": "Cookie", "surface": "Cookie"},
                {"name": "Fruit", "surface": "Fruit"},
                {"name": "Food", "surface": "Food"},
            ],
            "relations": [
                {"subject": "Apple", "relation_type": "is-a", "target": "Fruit", "statement": "Apple is a Fruit."},
                {"subject": "Grape", "relation_type": "is-a", "target": "Fruit", "statement": "Grape is a Fruit."},
                {"subject": "Cookie", "relation_type": "is-a", "target": "Food", "statement": "Cookie is a Food."},
                {"subject": "Fruit", "relation_type": "is-a", "target": "Food", "statement": "Fruit is a Food."},
            ],
            "attributes": [
                {"subject": "Food", "attribute_name": "edibility", "attribute_value": "edible", "statement": "Food is edible."}
            ],
            "suggested_questions": [],
            "uncertainties": [],
        }

    def compose_grounded_answer(self, *, question: str, grounded_bundle: dict[str, Any]) -> dict[str, Any]:
        relations = {tuple(item) for item in grounded_bundle.get("relations", []) if len(item) == 3}
        examples = grounded_bundle.get("examples", {})
        matched_concepts = grounded_bundle.get("matched_concepts", [])
        evidence_ids = [item["evidence_id"] for item in grounded_bundle.get("evidence", [])]
        event_ids = [item["event_id"] for item in grounded_bundle.get("events", [])]

        if question == "Apple belongs to what?":
            insufficient_memory = ("Apple", "is-a", "Fruit") not in relations
            answer = (
                "Based on my current memory, Apple belongs to Fruit."
                if not insufficient_memory
                else "I do not know yet what Apple belongs to from my current memory."
            )
            used_relations = [["Apple", "is-a", "Fruit"]] if not insufficient_memory else []
        elif question == "What examples does Fruit have?":
            fruit_examples = examples.get("Fruit", [])
            insufficient_memory = not fruit_examples
            answer = (
                "Based on my current memory, examples of Fruit include " + ", ".join(fruit_examples) + "."
                if fruit_examples
                else "I do not know yet what examples Fruit has from my current memory."
            )
            used_relations = []
        elif question == "Is Fruit a Food?":
            insufficient_memory = ("Fruit", "is-a", "Food") not in relations
            answer = (
                "Based on my current memory, yes, Fruit is a Food."
                if not insufficient_memory
                else "I do not know yet whether Fruit is a Food from my current memory."
            )
            used_relations = [["Fruit", "is-a", "Food"]] if not insufficient_memory else []
        elif question == "Is Food a Fruit?":
            insufficient_memory = ("Food", "is-a", "Fruit") not in relations
            answer = (
                "Based on my current memory, yes, Food is a Fruit."
                if not insufficient_memory
                else "I do not know yet whether Food is a Fruit from my current memory."
            )
            used_relations = [["Food", "is-a", "Fruit"]] if not insufficient_memory else []
        elif question == "What color is Cookie?":
            insufficient_memory = True
            answer = "I do not know yet what color Cookie is from my current memory."
            used_relations = []
        elif question == "Is Cookie a dessert?":
            insufficient_memory = True
            answer = "I do not know yet whether Cookie is a dessert from my current memory."
            used_relations = []
        else:
            insufficient_memory = True
            answer = "I do not know yet based on my current memory."
            used_relations = []

        return {
            "answer": answer,
            "used_concepts": matched_concepts,
            "used_relations": used_relations,
            "used_event_ids": event_ids,
            "used_evidence_ids": evidence_ids,
            "confidence": 0.74 if not insufficient_memory else 0.2,
            "insufficient_memory": insufficient_memory,
        }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    root = Path(__file__).resolve().parent
    data_root = root / "data" / "memory_retrieval_test"
    if data_root.exists():
        shutil.rmtree(data_root)

    engine = CognitiveEngine(data_root, language_hub=GroundedAnswerTestHub())
    engine.ingest_knowledge_with_llm(
        text=LESSON_TEXT,
        source_identity="grounded_memory_retrieval_test",
    )

    questions = [
        "Apple belongs to what?",
        "What examples does Fruit have?",
        "Is Fruit a Food?",
        "Is Food a Fruit?",
        "What color is Cookie?",
        "Is Cookie a dessert?",
    ]
    answers = {question: engine.answer_grounded_question(question=question) for question in questions}

    validation_observations = [
        f"{question} -> {result['answer']}"
        for question, result in answers.items()
    ]

    remaining_issues = []
    if not answers["Apple belongs to what?"]["used_relations"]:
        remaining_issues.append("Grounded answer for Apple classification did not cite the expected relation.")
    if answers["Is Food a Fruit?"]["insufficient_memory"] is not True:
        remaining_issues.append("Failure transparency failed for the inverse Food/Fruit question.")
    if answers["What color is Cookie?"]["insufficient_memory"] is not True:
        remaining_issues.append("Failure transparency failed for unknown Cookie color.")
    if answers["Is Cookie a dessert?"]["insufficient_memory"] is not True:
        remaining_issues.append("Failure transparency failed for unknown Cookie dessert status.")
    if not answers["What examples does Fruit have?"]["grounded_bundle"]["examples"].get("Fruit"):
        remaining_issues.append("Retriever bundle did not include Fruit examples.")

    full_report = {
        "data_root": str(data_root),
        "answers": answers,
        "validation_observations": validation_observations,
        "remaining_issues": remaining_issues,
    }
    report_path = data_root / "memory_retrieval_report.json"
    report_path.write_text(json.dumps(full_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Memory retrieval grounded QA test finished.")
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
        print("- No blocking issue found in grounded retrieval + answer composition.")


if __name__ == "__main__":
    main()
