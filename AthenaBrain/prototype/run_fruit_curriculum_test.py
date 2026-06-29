from __future__ import annotations

import shutil
import sys
from pathlib import Path

from athena_brain import CognitiveEngine


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    root = Path(__file__).resolve().parent
    data_root = root / "data" / "phase1_fruit_curriculum_test"
    if data_root.exists():
        shutil.rmtree(data_root)

    lessons = [
        {
            "statement": "苹果是一种水果。",
            "image_path": "../experiments/phase1_apple_test/inputs/apple_red_001.jpg",
            "sample_id": "curriculum_apple_001",
            "features": [
                {"category": "shape", "value": "The observed object looks roughly round.", "confidence": 0.82},
                {"category": "color", "value": "The observed object has a mostly red surface.", "confidence": 0.78},
                {"category": "surface", "value": "The observed object appears smooth.", "confidence": 0.7},
                {"category": "use", "value": "The user says it can be eaten.", "confidence": 0.75},
                {"category": "origin", "value": "The user says it grows from a plant.", "confidence": 0.68},
            ],
            "feedback": "这是苹果，可以吃，来自植物。",
        },
        {
            "statement": "桃子是一种水果。",
            "image_path": "../experiments/phase1_apple_test/inputs/peach_001.jpg",
            "sample_id": "curriculum_peach_001",
            "features": [
                {"category": "shape", "value": "The observed object looks roughly round.", "confidence": 0.78},
                {"category": "color", "value": "The observed object has a pink or orange surface.", "confidence": 0.74},
                {"category": "surface", "value": "The observed object may have a fuzzy surface.", "confidence": 0.62},
                {"category": "use", "value": "The user says it can be eaten.", "confidence": 0.75},
                {"category": "origin", "value": "The user says it grows from a plant.", "confidence": 0.68},
            ],
            "feedback": "这是桃子，也可以吃，也来自植物。",
        },
        {
            "statement": "梨是一种水果。",
            "image_path": "../experiments/phase1_apple_test/inputs/pear_001.jpg",
            "sample_id": "curriculum_pear_001",
            "features": [
                {"category": "shape", "value": "The observed object has a pear-like shape.", "confidence": 0.76},
                {"category": "color", "value": "The observed object has a green or yellow surface.", "confidence": 0.72},
                {"category": "surface", "value": "The observed object appears smooth.", "confidence": 0.68},
                {"category": "use", "value": "The user says it can be eaten.", "confidence": 0.75},
                {"category": "origin", "value": "The user says it grows from a plant.", "confidence": 0.68},
            ],
            "feedback": "这是梨，也可以吃，也来自植物。",
        },
        {
            "statement": "香蕉是一种水果。",
            "image_path": "../experiments/phase1_apple_test/inputs/banana_001.jpg",
            "sample_id": "curriculum_banana_001",
            "features": [
                {"category": "shape", "value": "The observed object is long and curved.", "confidence": 0.8},
                {"category": "color", "value": "The observed object has a mostly yellow surface.", "confidence": 0.78},
                {"category": "surface", "value": "The observed object has a peel.", "confidence": 0.72},
                {"category": "use", "value": "The user says it can be eaten.", "confidence": 0.75},
                {"category": "origin", "value": "The user says it grows from a plant.", "confidence": 0.68},
            ],
            "feedback": "这是香蕉，形状和苹果不一样，但也是水果。",
        },
        {
            "statement": "番茄是一种水果。",
            "image_path": "../experiments/phase1_apple_test/inputs/tomato_001.jpg",
            "sample_id": "curriculum_tomato_001",
            "features": [
                {"category": "shape", "value": "The observed object looks roughly round.", "confidence": 0.78},
                {"category": "color", "value": "The observed object has a mostly red surface.", "confidence": 0.76},
                {"category": "surface", "value": "The observed object appears smooth.", "confidence": 0.7},
                {"category": "use", "value": "The user says it can be eaten.", "confidence": 0.75},
                {"category": "origin", "value": "The user says it grows from a plant.", "confidence": 0.68},
                {"category": "boundary_note", "value": "The user says people may debate whether it is fruit or vegetable.", "confidence": 0.6},
            ],
            "feedback": "番茄也可以算水果，但它可能和蔬菜的边界有关。",
        },
        {
            "statement": "塑料苹果不是一种水果。",
            "image_path": "../experiments/phase1_apple_test/inputs/plastic_apple_001.jpg",
            "sample_id": "curriculum_plastic_apple_001",
            "features": [
                {"category": "shape", "value": "The observed object looks roughly round.", "confidence": 0.8},
                {"category": "color", "value": "The observed object has a mostly red surface.", "confidence": 0.78},
                {"category": "surface", "value": "The observed object appears shiny and artificial.", "confidence": 0.72},
                {"category": "use", "value": "The user says it should not be eaten.", "confidence": 0.8},
                {"category": "origin", "value": "The user says it is made of plastic.", "confidence": 0.82},
            ],
            "feedback": "它看起来像苹果，但它是塑料做的，不是水果。",
        },
    ]

    for lesson in lessons:
        engine = CognitiveEngine(data_root)
        engine.learn_from_guided_example(
            user_statement=lesson["statement"],
            image_path=lesson["image_path"],
            sample_id=lesson["sample_id"],
            perception_features=lesson["features"],
            user_feedback=[
                {
                    "type": "lesson_feedback",
                    "content": lesson["feedback"],
                }
            ],
            source_identity="user",
            source_diversity="single_user",
            independence_score=0.8,
        )

    engine = CognitiveEngine(data_root)
    print("Fruit curriculum test finished.")
    print()
    print("Fruit concept:")
    print(engine.describe_concept("Fruit"))
    print()
    print("PlasticApple concept:")
    print(engine.describe_concept("PlasticApple"))
    print()
    print(f"Records saved to: {data_root}")


if __name__ == "__main__":
    main()
