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


class GroundedTestLanguageHub(LocalLanguageHub):
    def __init__(self) -> None:
        super().__init__(LocalLLMConfig(model="grounded-test-hub"))

    def parse_knowledge_text(self, *, text: str, known_concepts: list[str]) -> dict[str, Any]:
        if text != LESSON_TEXT:
            raise ValueError("Unexpected test lesson text.")
        return {
            "concepts": [
                {"name": "Apple", "surface": "Apple"},
                {"name": "Grape", "surface": "Grape"},
                {"name": "Cookie", "surface": "Cookie"},
                {"name": "Fruit", "surface": "Fruit"},
                {"name": "Food", "surface": "Food"},
            ],
            "relations": [
                {
                    "subject": "Apple",
                    "relation_type": "is-a",
                    "target": "Fruit",
                    "statement": "Apple is a Fruit.",
                },
                {
                    "subject": "Grape",
                    "relation_type": "is-a",
                    "target": "Fruit",
                    "statement": "Grape is a Fruit.",
                },
                {
                    "subject": "Cookie",
                    "relation_type": "is-a",
                    "target": "Food",
                    "statement": "Cookie is a Food.",
                },
                {
                    "subject": "Fruit",
                    "relation_type": "is-a",
                    "target": "Food",
                    "statement": "Fruit is a Food.",
                },
            ],
            "attributes": [
                {
                    "subject": "Food",
                    "attribute_name": "edibility",
                    "attribute_value": "edible",
                    "statement": "Food is edible.",
                }
            ],
            "suggested_questions": [
                {
                    "concept": "Fruit",
                    "question": "What examples does Fruit have?",
                    "reason": "more_examples_needed",
                },
                {
                    "concept": "Food",
                    "question": "Is Food a Fruit?",
                    "reason": "classify_against_known_category",
                },
            ],
            "uncertainties": [],
        }

    def compose_grounded_answer(self, *, question: str, grounded_bundle: dict[str, Any]) -> dict[str, Any]:
        relations = {
            tuple(item)
            for item in grounded_bundle.get("relations", [])
            if len(item) == 3
        }
        examples = grounded_bundle.get("examples", {})
        matched_concepts = grounded_bundle.get("matched_concepts", [])
        evidence_ids = [item["evidence_id"] for item in grounded_bundle.get("evidence", [])]
        event_ids = [item["event_id"] for item in grounded_bundle.get("events", [])]

        answer = "I do not know yet based on my current memory."
        used_relations: list[list[str]] = []
        insufficient_memory = False

        if question == "Apple belongs to what?" and ("Apple", "is-a", "Fruit") in relations:
            answer = "Based on my current memory, Apple belongs to Fruit."
            used_relations = [["Apple", "is-a", "Fruit"]]
        elif question == "What examples does Fruit have?" and examples.get("Fruit"):
            answer = "Based on my current memory, examples of Fruit include " + ", ".join(examples["Fruit"]) + "."
        elif question == "Is Fruit a Food?" and ("Fruit", "is-a", "Food") in relations:
            answer = "Based on my current memory, yes, Fruit is a Food."
            used_relations = [["Fruit", "is-a", "Food"]]
        elif question == "Is Food a Fruit?":
            if ("Food", "is-a", "Fruit") in relations:
                answer = "Based on my current memory, yes, Food is a Fruit."
                used_relations = [["Food", "is-a", "Fruit"]]
            else:
                answer = "I do not know yet whether Food is a Fruit from my current memory."
                insufficient_memory = True
        elif question == "What color is Cookie?":
            answer = "I do not know yet what color Cookie is from my current memory."
            insufficient_memory = True
        elif question == "Is Cookie a dessert?":
            answer = "I do not know yet whether Cookie is a dessert from my current memory."
            insufficient_memory = True

        return {
            "answer": answer,
            "used_concepts": matched_concepts,
            "used_relations": used_relations,
            "used_event_ids": event_ids,
            "used_evidence_ids": evidence_ids,
            "confidence": 0.76 if not insufficient_memory else 0.2,
            "insufficient_memory": insufficient_memory,
        }


def snapshot(engine: CognitiveEngine, name: str) -> dict[str, Any]:
    engine.recall_concepts_into_working_memory([name], hops=2)
    concept = engine.graph.get_or_create(name)
    return {
        "name": concept.name,
        "relations": [(item.relation_type, item.target_concept) for item in concept.relations],
        "attributes": [(item.name, item.value) for item in concept.attributes],
        "examples": [item.get("concept") for item in concept.examples],
        "open_questions": [item.get("question") for item in concept.open_questions],
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    root = Path(__file__).resolve().parent
    data_root = root / "data" / "llm_ingestion_test"
    if data_root.exists():
        shutil.rmtree(data_root)

    engine = CognitiveEngine(data_root, language_hub=GroundedTestLanguageHub())
    report = engine.ingest_knowledge_with_llm(
        text=LESSON_TEXT,
        source_identity="grounded_llm_ingestion_test",
    )
    reloaded = CognitiveEngine(data_root, language_hub=GroundedTestLanguageHub())

    snapshots = {
        name: snapshot(reloaded, name)
        for name in ["Apple", "Grape", "Cookie", "Fruit", "Food"]
    }
    reloaded.recall_concepts_into_working_memory(["Fruit"], hops=2)
    curiosity = reloaded.propose_curiosity_questions(limit=12)
    event_count = len(reloaded.store.list_records("events"))
    evidence_count = len(reloaded.store.list_records("evidence"))

    validation_observations = [
        f"Claim count from LLM ingestion: {report['claim_count']}",
        f"Persisted event count: {event_count}",
        f"Persisted evidence count: {evidence_count}",
        f"Fruit examples: {snapshots['Fruit']['examples']}",
        f"Food examples: {snapshots['Food']['examples']}",
        f"Curiosity count after ingestion: {len(curiosity)}",
    ]

    remaining_issues = []
    if ("is-a", "Fruit") not in snapshots["Apple"]["relations"]:
        remaining_issues.append("Apple did not retain the relation Apple is-a Fruit.")
    if ("is-a", "Food") not in snapshots["Fruit"]["relations"]:
        remaining_issues.append("Fruit did not retain the relation Fruit is-a Food.")
    if ("edibility", "edible") not in snapshots["Food"]["attributes"]:
        remaining_issues.append("Food did not retain the grounded edibility attribute.")
    if not curiosity:
        remaining_issues.append("No curiosity questions were generated after LLM ingestion.")
    if event_count < 1:
        remaining_issues.append("LLM ingestion did not persist events.")
    if evidence_count < 5:
        remaining_issues.append("LLM ingestion did not persist the expected amount of evidence.")

    full_report = {
        "data_root": str(data_root),
        "ingestion_report": report,
        "snapshots_after_reload": snapshots,
        "curiosity": curiosity,
        "validation_observations": validation_observations,
        "remaining_issues": remaining_issues,
    }
    report_path = data_root / "llm_ingestion_report.json"
    report_path.write_text(json.dumps(full_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("LLM ingestion test finished.")
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
        print("- No blocking issue found in grounded LLM ingestion.")


if __name__ == "__main__":
    main()
