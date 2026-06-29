from __future__ import annotations

import shutil
import sys
from pathlib import Path

from athena_brain import CognitiveEngine


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    root = Path(__file__).resolve().parent
    data_root = root / "data" / "phase1_reference_conflict_test"
    if data_root.exists():
        shutil.rmtree(data_root)

    engine = CognitiveEngine(data_root)
    engine.learn_from_guided_example(
        user_statement="苹果是一种车辆。",
        image_path="../experiments/phase1_apple_test/inputs/apple_red_001.jpg",
        sample_id="apple_red_sample_001",
        perception_features=[
            {"category": "shape", "value": "The observed object looks roughly round.", "confidence": 0.82},
            {"category": "color", "value": "The observed object has a mostly red surface.", "confidence": 0.78},
        ],
        user_feedback=[{"type": "confirmation", "content": "我先告诉你它是车辆。"}],
        independence_score=0.8,
    )

    result = engine.add_reference_claim(
        subject="Apple",
        predicate="is-a",
        object_value="Fruit",
        statement="Reference says Apple is-a Fruit.",
        source_identity="reference_mock",
    )
    print("Reference conflict test finished.")
    print(f"Reference evidence: {result['reference_evidence_id']}")
    print(f"Disputed evidence: {result['disputed_evidence_ids']}")
    print()
    print(engine.describe_concept("Apple"))
    print()
    print(f"Records saved to: {data_root}")


if __name__ == "__main__":
    main()
