from __future__ import annotations


class AbstractionPolicy:
    """Rules for promoting observed variations into concept-level abstractions."""

    def classify(
        self,
        *,
        distinct_value_count: int,
        evidence_count: int,
        independent_sample_count: int,
        base_confidence: float,
    ) -> dict[str, object]:
        if (
            distinct_value_count >= 2
            and evidence_count >= 2
            and independent_sample_count >= 2
            and base_confidence >= 0.55
        ):
            return {
                "status": "generalized_attribute",
                "confidence": min(0.85, base_confidence + 0.15),
                "reason": "multiple_values_supported_by_independent_samples",
            }

        if distinct_value_count >= 2:
            return {
                "status": "generalized_candidate",
                "confidence": base_confidence,
                "reason": "multiple_values_observed_but_independent_evidence_is_still_limited",
            }

        return {
            "status": "not_generalized",
            "confidence": base_confidence,
            "reason": "insufficient_variation",
        }
