from __future__ import annotations

from .models import Perception, PerceptionFeature


class PerceptionInterface:
    """Vision/perception boundary.

    Phase 1 intentionally allows mocked/manual features. A real vision model can
    replace this class later without changing the cognition layer.
    """

    def perceive_image(
        self,
        image_path: str,
        *,
        features: list[dict[str, object]],
        sample_id: str | None = None,
        hypotheses: list[dict[str, object]] | None = None,
    ) -> Perception:
        return Perception(
            input_ref=image_path,
            sample_id=sample_id,
            features=[
                PerceptionFeature(
                    category=str(feature["category"]),
                    value=str(feature["value"]),
                    confidence=float(feature.get("confidence", 0.5)),
                    evidence="image observation",
                )
                for feature in features
            ],
            unverified_hypotheses=hypotheses or [],
        )
