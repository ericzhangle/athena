from __future__ import annotations

import shutil
import sys
from pathlib import Path

from athena_brain import CognitiveEngine


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    root = Path(__file__).resolve().parent
    data_root = root / "data" / "phase1_fruit_generalization_test"
    if data_root.exists():
        shutil.rmtree(data_root)

    examples = [
        {
            "statement": "苹果是一种水果。",
            "image_path": "../experiments/phase1_apple_test/inputs/apple_red_001.jpg",
            "sample_id": "fruit_test_apple_001",
            "features": [
                {"category": "shape", "value": "The observed object looks roughly round.", "confidence": 0.82},
                {"category": "color", "value": "The observed object has a mostly red surface.", "confidence": 0.78},
                {"category": "surface", "value": "The observed object appears smooth.", "confidence": 0.7},
                {"category": "use", "value": "The user says it can be eaten.", "confidence": 0.75},
            ],
            "feedback": "这是苹果，可以吃。",
        },
        {
            "statement": "桃子是一种水果。",
            "image_path": "../experiments/phase1_apple_test/inputs/peach_001.jpg",
            "sample_id": "fruit_test_peach_001",
            "features": [
                {"category": "shape", "value": "The observed object looks roughly round.", "confidence": 0.78},
                {"category": "color", "value": "The observed object has a pink or orange surface.", "confidence": 0.74},
                {"category": "surface", "value": "The observed object may have a fuzzy surface.", "confidence": 0.62},
                {"category": "use", "value": "The user says it can be eaten.", "confidence": 0.75},
            ],
            "feedback": "这是桃子，也可以吃。",
        },
        {
            "statement": "梨是一种水果。",
            "image_path": "../experiments/phase1_apple_test/inputs/pear_001.jpg",
            "sample_id": "fruit_test_pear_001",
            "features": [
                {"category": "shape", "value": "The observed object has a pear-like shape.", "confidence": 0.76},
                {"category": "color", "value": "The observed object has a green or yellow surface.", "confidence": 0.72},
                {"category": "surface", "value": "The observed object appears smooth.", "confidence": 0.68},
                {"category": "use", "value": "The user says it can be eaten.", "confidence": 0.75},
            ],
            "feedback": "这是梨，也是一种可以吃的水果。",
        },
    ]

    result = None
    for item in examples:
        engine = CognitiveEngine(data_root)
        result = engine.learn_from_guided_example(
            user_statement=item["statement"],
            image_path=item["image_path"],
            sample_id=item["sample_id"],
            perception_features=item["features"],
            user_feedback=[
                {
                    "type": "confirmation",
                    "content": item["feedback"],
                }
            ],
            source_identity="user",
            source_diversity="single_user",
            independence_score=0.8,
        )

    engine = CognitiveEngine(data_root)
    print("Fruit generalization test finished.")
    if result:
        print(f"Last Experience: {result['experience_id']}")
    print()
    print("Fruit concept:")
    print(engine.describe_concept("Fruit"))
    print()
    print("Apple concept:")
    print(engine.describe_concept("Apple"))
    print()
    print(f"Records saved to: {data_root}")


if __name__ == "__main__":
    main()
