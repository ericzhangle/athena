from __future__ import annotations

import sys
from pathlib import Path

from athena_brain import CognitiveEngine


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    root = Path(__file__).resolve().parent
    data_root = root / "data" / "phase1_apple_test"

    engine = CognitiveEngine(data_root)
    result = engine.learn_from_guided_example(
        user_statement="苹果是一种水果。",
        image_path="../experiments/phase1_apple_test/inputs/apple_green_001.jpg",
        sample_id="apple_green_sample_001",
        perception_features=[
            {
                "category": "shape",
                "value": "The observed object looks roughly round.",
                "confidence": 0.8,
            },
            {
                "category": "color",
                "value": "The observed object has a mostly green surface.",
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
                "content": "是的，这也是苹果，只是它是绿色的。",
            },
            {
                "type": "correction_or_expansion",
                "content": "苹果不一定都是红色，有些苹果是绿色或黄色的。",
            },
        ],
        source_identity="user",
        source_diversity="single_user",
        independence_score=0.8,
    )

    print("BabyBrain Incremental Apple Learning finished.")
    print(f"Experience: {result['experience_id']}")
    print(f"Sleep Report: {result['sleep_report_id']}")
    print(f"Updated Concept: {result['concept_id']}")
    print()
    print("Athena response:")
    print(result["response"])
    print()
    print(f"Records saved to: {data_root}")


if __name__ == "__main__":
    main()
