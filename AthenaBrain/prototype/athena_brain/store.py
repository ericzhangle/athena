from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import to_dict


class JsonMemoryStore:
    """Small durable store for prototype cognition records.

    This is intentionally simple. The important property is not database power;
    it is that Experience, Perception, State and Concept records are persisted
    separately and can be traced later.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.collections = {
            "states": self.root / "states",
            "perceptions": self.root / "perceptions",
            "experiences": self.root / "experiences",
            "evidence": self.root / "evidence",
            "concepts": self.root / "concepts",
            "rules": self.root / "rules",
            "reports": self.root / "reports",
        }
        for path in self.collections.values():
            path.mkdir(parents=True, exist_ok=True)

    def save(self, collection: str, record_id: str, payload: Any) -> Path:
        if collection not in self.collections:
            raise ValueError(f"Unknown collection: {collection}")

        path = self.collections[collection] / f"{record_id}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(to_dict(payload), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return path

    def load(self, collection: str, record_id: str) -> dict[str, Any]:
        path = self.collections[collection] / f"{record_id}.json"
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def list_records(self, collection: str) -> list[Path]:
        if collection not in self.collections:
            raise ValueError(f"Unknown collection: {collection}")
        return sorted(self.collections[collection].glob("*.json"))
