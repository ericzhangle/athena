from __future__ import annotations

import re


class AttributeNormalizer:
    """Tiny normalization layer for early prototype attributes.

    This is deliberately conservative. It does not try to understand the world;
    it only prevents obvious string-level noise from becoming false cognition.
    """

    COLOR_WORDS = {
        "red": "red",
        "green": "green",
        "yellow": "yellow",
        "blue": "blue",
        "orange": "orange",
        "purple": "purple",
        "black": "black",
        "white": "white",
        "brown": "brown",
    }

    SHAPE_WORDS = {
        "round": "round",
        "oval": "oval",
        "long": "long",
        "flat": "flat",
        "sphere": "round",
        "spherical": "round",
    }

    SURFACE_WORDS = {
        "smooth": "smooth",
        "rough": "rough",
        "reflective": "reflective",
        "shiny": "reflective",
        "matte": "matte",
    }

    def normalize(self, category: str, value: str) -> dict[str, object]:
        category = category.strip().lower()
        lowered = value.lower()

        if category == "color":
            tokens = self._extract_known_tokens(lowered, self.COLOR_WORDS)
            return {
                "category": category,
                "canonical_values": tokens or [self._compact(value)],
                "comparison_mode": "variation",
            }

        if category == "shape":
            tokens = self._extract_known_tokens(lowered, self.SHAPE_WORDS)
            return {
                "category": category,
                "canonical_values": tokens or [self._compact(value)],
                "comparison_mode": "variation",
            }

        if category == "surface":
            tokens = self._extract_known_tokens(lowered, self.SURFACE_WORDS)
            return {
                "category": category,
                "canonical_values": tokens or [self._compact(value)],
                "comparison_mode": "compatible_traits",
            }

        return {
            "category": category,
            "canonical_values": [self._compact(value)],
            "comparison_mode": "variation",
        }

    def same_or_compatible(self, category: str, left: str, right: str) -> bool:
        left_norm = self.normalize(category, left)
        right_norm = self.normalize(category, right)
        left_values = set(left_norm["canonical_values"])
        right_values = set(right_norm["canonical_values"])

        if left_values == right_values:
            return True

        if left_norm["comparison_mode"] == "compatible_traits":
            # Smooth and smooth+reflective should not be treated as conflict.
            return bool(left_values.intersection(right_values))

        return False

    def variation_values(self, category: str, values: list[str]) -> list[str]:
        normalized_values = []
        for value in values:
            normalized = self.normalize(category, value)
            normalized_values.extend(str(item) for item in normalized["canonical_values"])
        return sorted(set(normalized_values))

    def _extract_known_tokens(self, lowered: str, mapping: dict[str, str]) -> list[str]:
        tokens = []
        for word, canonical in mapping.items():
            if re.search(rf"\b{re.escape(word)}\b", lowered) and canonical not in tokens:
                tokens.append(canonical)
        return tokens

    def _compact(self, value: str) -> str:
        return " ".join(value.lower().strip().split())
