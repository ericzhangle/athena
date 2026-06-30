from __future__ import annotations

from .models import Claim, Evidence, evidence_from_dict
from .store import JsonMemoryStore


ACTIVE_STATUSES = {"provisional", "confirmed"}
INACTIVE_STATUSES = {"disputed", "invalidated", "contaminated"}


class EvidenceLedger:
    """Tracks evidence status and validation history."""

    def __init__(self, store: JsonMemoryStore, *, autoload: bool = True) -> None:
        self.store = store
        self.evidence: dict[str, Evidence] = {}
        if autoload:
            self._load_existing()

    def add_evidence(
        self,
        *,
        claim: Claim,
        source_type: str,
        source_identity: str,
        refs: list[str],
        confidence: float,
        sample_id: str | None = None,
        status: str = "provisional",
    ) -> Evidence:
        evidence = Evidence(
            claim=claim,
            source_type=source_type,
            source_identity=source_identity,
            refs=refs,
            confidence=confidence,
            sample_id=sample_id,
            status=status,
        )
        self.evidence[evidence.evidence_id] = evidence
        self.store.save("evidence", evidence.evidence_id, evidence)
        return evidence

    def invalidate_by_ref(self, ref: str, *, reason: str) -> list[Evidence]:
        affected = [
            item
            for item in self.evidence.values()
            if ref in item.refs or item.sample_id == ref or any(ref in evidence_ref for evidence_ref in item.refs)
        ]
        for item in affected:
            item.add_validation_event(
                event_type="invalidate",
                reason=reason,
                new_status="invalidated",
            )
            self.store.save("evidence", item.evidence_id, item)
        return affected

    def find_claims(
        self,
        *,
        subject: str,
        predicate: str,
    ) -> list[Evidence]:
        return [
            item
            for item in self.evidence.values()
            if item.claim.subject == subject and item.claim.predicate == predicate
        ]

    def dispute(self, evidence_id: str, *, reason: str) -> Evidence | None:
        item = self.evidence.get(evidence_id)
        if item is None:
            return None
        item.add_validation_event(
            event_type="dispute",
            reason=reason,
            new_status="disputed",
        )
        self.store.save("evidence", item.evidence_id, item)
        return item

    def status_map(self) -> dict[str, str]:
        return {evidence_id: item.status for evidence_id, item in self.evidence.items()}

    def sample_id_map(self) -> dict[str, str]:
        return {
            evidence_id: item.sample_id
            for evidence_id, item in self.evidence.items()
            if item.sample_id
        }

    def is_active(self, evidence_id: str) -> bool:
        item = self.evidence.get(evidence_id)
        if item is None:
            return True
        return item.status in ACTIVE_STATUSES

    def clear(self) -> None:
        self.evidence = {}

    def load_evidence_ids(self, evidence_ids: list[str]) -> list[Evidence]:
        loaded = []
        for evidence_id in evidence_ids:
            item = self.evidence.get(evidence_id)
            if item is not None:
                loaded.append(item)
                continue
            try:
                payload = self.store.load("evidence", evidence_id)
                item = evidence_from_dict(payload)
            except (OSError, KeyError, ValueError, TypeError):
                continue
            self.evidence[item.evidence_id] = item
            loaded.append(item)
        return loaded

    def _load_existing(self) -> None:
        for path in self.store.list_records("evidence"):
            try:
                import json

                with path.open("r", encoding="utf-8") as handle:
                    item = evidence_from_dict(json.load(handle))
                self.evidence[item.evidence_id] = item
            except (OSError, KeyError, ValueError, TypeError):
                continue
