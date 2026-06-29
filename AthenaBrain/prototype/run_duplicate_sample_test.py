from __future__ import annotations

import shutil
import sys
from pathlib import Path

from athena_brain import CognitiveEngine


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    root = Path(__file__).resolve().parent
    data_root = root / "data" / "phase1_duplicate_sample_test"
    if data_root.exists():
        shutil.rmtree(data_root)

    for _ in range(3):
        engine = CognitiveEngine(data_root)
        result = engine.learn_from_guided_example(
            user_statement="苹果是一种水果。",
            image_path="../experiments/phase1_apple_test/inputs/apple_red_001.jpg",
            sample_id="apple_red_sample_001",
            perception_features=[
                {
                    "category": "shape",
                    "value": "The observed object looks roughly round.",
                    "confidence": 0.82,
                },
                {
                    "category": "color",
                    "value": "The observed object has a mostly red surface.",
                    "confidence": 0.78,
                },
                {
                    "category": "surface",
                    "value": "The observed object appears smooth.",
                    "confidence": 0.68,
                },
            ],
            user_feedback=[
                {
                    "type": "confirmation",
                    "content": "这是同一个红色苹果样本。",
                },
            ],
            independence_score=0.2,
        )

    print("Duplicate sample test finished.")
    print(f"Updated Concept: {result['concept_id']}")
    print()
    print(result["response"])
    print()
    print(f"Records saved to: {data_root}")


if __name__ == "__main__":
    main()
