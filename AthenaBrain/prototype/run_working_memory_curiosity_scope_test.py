from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from athena_brain import CognitiveEngine


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    root = Path(__file__).resolve().parent
    data_root = root / "data" / "working_memory_curiosity_scope_test"
    if data_root.exists():
        shutil.rmtree(data_root)

    engine = CognitiveEngine(data_root)
    lessons = [
        "Apple is a Fruit.",
        "Grape is a Fruit.",
        "Fruit is a Food.",
        "Car is a Vehicle.",
    ]
    for lesson in lessons:
        engine.ingest_knowledge_text(text=lesson, source_identity="working_memory_scope_test")

    reloaded = CognitiveEngine(data_root)
    dormant_questions = reloaded.propose_curiosity_questions(limit=20)

    reloaded.recall_concepts_into_working_memory(["Fruit"], hops=2)
    fruit_questions = reloaded.propose_curiosity_questions(limit=20)
    fruit_scope = reloaded.working_memory_summary()

    reloaded.recall_concepts_into_working_memory(["Car"], hops=2)
    car_questions = reloaded.propose_curiosity_questions(limit=20)
    car_scope = reloaded.working_memory_summary()

    validation_observations = [
        f"Dormant curiosity count without working memory: {len(dormant_questions)}",
        f"Fruit working-memory scope: {fruit_scope}",
        f"Fruit question concepts: {sorted({item['concept'] for item in fruit_questions})}",
        f"Car working-memory scope: {car_scope}",
        f"Car question concepts: {sorted({item['concept'] for item in car_questions})}",
    ]

    remaining_issues = []
    if dormant_questions:
        remaining_issues.append("Dormant long-term memories still generated curiosity without any active working memory.")
    if any(item["concept"] in {"Car", "Vehicle"} for item in fruit_questions):
        remaining_issues.append("Fruit recall leaked unrelated vehicle curiosity into the active question set.")
    if fruit_questions and not all(
        item["concept"] in set(fruit_scope["active_concepts"])
        for item in fruit_questions
    ):
        remaining_issues.append("Fruit curiosity was generated outside the active working-memory concept scope.")
    if any(item["concept"] in {"Fruit", "Apple", "Grape", "Food"} for item in car_questions):
        remaining_issues.append("Car recall leaked unrelated fruit curiosity into the active question set.")
    if car_questions and not all(
        item["concept"] in set(car_scope["active_concepts"])
        for item in car_questions
    ):
        remaining_issues.append("Car curiosity was generated outside the active working-memory concept scope.")

    full_report = {
        "data_root": str(data_root),
        "dormant_questions": dormant_questions,
        "fruit_scope": fruit_scope,
        "fruit_questions": fruit_questions,
        "car_scope": car_scope,
        "car_questions": car_questions,
        "validation_observations": validation_observations,
        "remaining_issues": remaining_issues,
    }
    report_path = data_root / "working_memory_curiosity_scope_report.json"
    report_path.write_text(json.dumps(full_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Working-memory curiosity scope test finished.")
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
        print("- No blocking issue found in working-memory-scoped curiosity.")


if __name__ == "__main__":
    main()
