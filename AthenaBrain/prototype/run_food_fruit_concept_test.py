from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from athena_brain import CognitiveEngine


def concept_snapshot(engine: CognitiveEngine, name: str) -> dict[str, Any]:
    concept = engine.graph.get_or_create(name)
    return {
        "name": concept.name,
        "maturity": concept.maturity,
        "relations": [
            {
                "relation_type": relation.relation_type,
                "target": relation.target_concept,
                "confidence": relation.confidence,
            }
            for relation in concept.relations
        ],
        "attributes": [
            {
                "name": attribute.name,
                "value": attribute.value,
                "scope": attribute.scope,
                "confidence": attribute.confidence,
            }
            for attribute in concept.attributes
        ],
        "examples": [item.get("concept") for item in concept.examples],
        "counterexamples": [item.get("concept") for item in concept.counterexamples],
        "open_questions": [
            {
                "question": item.get("question"),
                "reason": item.get("reason"),
                "status": item.get("status", "open"),
            }
            for item in concept.open_questions
        ],
    }


def top_questions(engine: CognitiveEngine, *, limit: int = 12) -> list[dict[str, Any]]:
    return engine.propose_curiosity_questions(limit=limit)


def has_food_fruit_question(questions: list[dict[str, Any]]) -> bool:
    return bool(question_groups(questions)["hierarchy"])


def question_groups(questions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {
        "hierarchy": [],
        "examples": [],
        "identity": [],
        "attribute_scope": [],
        "relation_meaning": [],
        "other": [],
    }
    for question in questions:
        text = str(question.get("question", ""))
        reason = str(question.get("reason", ""))
        if "Food" in text and "Fruit" in text:
            groups["hierarchy"].append(question)
            continue
        if reason in {"classify_against_known_category", "similarity_based_candidate_category"} and (
            "Food" in text or "Fruit" in text
        ):
            groups["hierarchy"].append(question)
        elif reason == "more_examples_needed":
            groups["examples"].append(question)
        elif "identity" in reason or reason == "mentioned_concept_needs_identity":
            groups["identity"].append(question)
        elif reason == "attribute_scope_unclear":
            groups["attribute_scope"].append(question)
        elif "relation" in reason:
            groups["relation_meaning"].append(question)
        else:
            groups["other"].append(question)
    return groups


def write_report(data_root: Path, report: dict[str, Any]) -> None:
    report_path = data_root / "food_fruit_concept_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Food-Fruit Concept Formation Test",
        "",
        "## Purpose",
        "Validate whether Athena can form a small knowledge tree from events, not from a prebuilt taxonomy.",
        "",
        "## Lessons",
    ]
    for item in report["lessons"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Curiosity Before External Answer"])
    for question in report["questions_before_answer"]:
        lines.append(f"- {question['concept']} / {question['reason']}: {question['question']}")
    lines.extend(["", "## Curiosity Groups"])
    for group_name, items in report["question_groups_before_answer"].items():
        lines.append(f"- {group_name}: {len(items)}")
    lines.extend(["", "## External Answer"])
    lines.append(report["external_answer"] or "No external answer was provided because Athena did not ask a Food/Fruit relation question.")
    lines.extend(["", "## Validation Observations"])
    for item in report["validation_observations"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Remaining Issues"])
    for item in report["remaining_issues"]:
        lines.append(f"- {item}")
    (data_root / "food_fruit_concept_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    root = Path(__file__).resolve().parent
    data_root = root / "data" / "v1_food_fruit_concept_test"
    if data_root.exists():
        shutil.rmtree(data_root)

    lessons = [
        "Apple is a Fruit.",
        "Apple can be eaten.",
        "Grape is a Fruit.",
        "Grape can be eaten.",
        "Cookie is a Food.",
        "Food is something edible.",
    ]

    engine = CognitiveEngine(data_root)
    lesson_reports = []
    for lesson in lessons:
        lesson_reports.append(
            engine.ingest_knowledge_text(
                text=lesson,
                source_identity="v1_food_fruit_curriculum",
            )
        )

    questions_before = top_questions(engine)
    groups_before = question_groups(questions_before)
    external_answer = None
    external_report = None
    if has_food_fruit_question(questions_before):
        external_answer = "Fruit is a Food."
        external_report = engine.ingest_knowledge_text(
            text=external_answer,
            source_identity="mock_reference_answer_for_food_fruit_relation",
        )

    # Reload from disk to verify persistence rather than relying on the live object.
    reloaded = CognitiveEngine(data_root)
    snapshots = {
        name: concept_snapshot(reloaded, name)
        for name in ["Apple", "Grape", "Fruit", "Cookie", "Food"]
    }
    questions_after_reload = top_questions(reloaded)
    event_count = len(reloaded.store.list_records("events"))

    food_examples = set(snapshots["Food"]["examples"])
    fruit_examples = set(snapshots["Fruit"]["examples"])
    fruit_relations = {
        (relation["relation_type"], relation["target"])
        for relation in snapshots["Fruit"]["relations"]
    }

    validation_observations = [
        f"Event records persisted: {event_count}",
        f"Fruit examples after learning: {sorted(fruit_examples)}",
        f"Food examples after learning: {sorted(food_examples)}",
        f"Fruit relations after external answer: {sorted(fruit_relations)}",
        (
            "Athena asked a Food/Fruit relation question before the external answer."
            if has_food_fruit_question(questions_before)
            else "Athena did not ask a Food/Fruit relation question before the external answer."
        ),
        "Curiosity groups before answer: "
        + ", ".join(
            f"{group_name}={len(items)}"
            for group_name, items in groups_before.items()
        ),
    ]

    remaining_issues = []
    if "Apple" not in fruit_examples or "Grape" not in fruit_examples:
        remaining_issues.append("Fruit examples did not fully consolidate Apple and Grape.")
    if "Cookie" not in food_examples:
        remaining_issues.append("Food examples did not consolidate Cookie.")
    if external_answer and "Fruit" not in food_examples:
        remaining_issues.append("Food did not absorb Fruit as an example after 'Fruit is a Food'.")
    if external_answer and ("is-a", "Food") not in fruit_relations:
        remaining_issues.append("Fruit did not retain the relation Fruit is-a Food after reload.")
    if not has_food_fruit_question(questions_before):
        remaining_issues.append("Curiosity did not surface the expected Food/Fruit hierarchy confusion.")
    if not groups_before["examples"]:
        remaining_issues.append("Curiosity did not surface example-expansion questions.")
    if not groups_before["identity"]:
        remaining_issues.append("Curiosity did not surface identity questions for new concepts.")

    report = {
        "data_root": str(data_root),
        "lessons": lessons,
        "lesson_report_ids": [item["report_id"] for item in lesson_reports],
        "questions_before_answer": questions_before,
        "question_groups_before_answer": groups_before,
        "external_answer": external_answer,
        "external_report_id": external_report["report_id"] if external_report else None,
        "snapshots_after_reload": snapshots,
        "questions_after_reload": questions_after_reload,
        "event_count": event_count,
        "validation_observations": validation_observations,
        "remaining_issues": remaining_issues,
    }
    write_report(data_root, report)

    print("Food-Fruit concept formation test finished.")
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
        print("- No blocking issue found in this small test.")
    print()
    print("Top questions after reload:")
    for question in questions_after_reload[:8]:
        print(f"- {question['concept']} / {question['reason']}: {question['question']}")


if __name__ == "__main__":
    main()
