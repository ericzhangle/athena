from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


@dataclass
class EvidenceRef:
    ref_id: str
    source_type: str
    summary: str


@dataclass
class Claim:
    statement: str
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None


@dataclass
class ValidationEvent:
    event_type: str
    reason: str
    previous_status: str
    new_status: str
    timestamp: str = field(default_factory=now_iso)


@dataclass
class Evidence:
    claim: Claim
    source_type: str
    source_identity: str
    refs: list[str]
    status: str = "provisional"
    confidence: float = 0.6
    evidence_id: str = field(default_factory=lambda: new_id("evidence"))
    timestamp: str = field(default_factory=now_iso)
    sample_id: str | None = None
    validation_events: list[ValidationEvent] = field(default_factory=list)

    def add_validation_event(self, event_type: str, reason: str, new_status: str) -> None:
        self.validation_events.append(
            ValidationEvent(
                event_type=event_type,
                reason=reason,
                previous_status=self.status,
                new_status=new_status,
            )
        )
        self.status = new_status


@dataclass
class PerceptionFeature:
    category: str
    value: str
    confidence: float
    evidence: str = "observation"


@dataclass
class Perception:
    input_ref: str
    features: list[PerceptionFeature]
    sample_id: str | None = None
    source_model: str = "manual_or_mock_interface"
    perception_id: str = field(default_factory=lambda: new_id("perception"))
    timestamp: str = field(default_factory=now_iso)
    unverified_hypotheses: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Experience:
    raw_inputs: list[dict[str, Any]]
    perception_refs: list[str]
    athena_questions: list[dict[str, Any]]
    user_feedback: list[dict[str, Any]]
    tags: list[str]
    sample_id: str | None = None
    source_identity: str = "user"
    source_diversity: str = "single_user"
    independence_score: float = 0.5
    experience_id: str = field(default_factory=lambda: new_id("experience"))
    timestamp: str = field(default_factory=now_iso)
    processed: bool = False
    immutable: bool = True


@dataclass
class ConceptAttribute:
    name: str
    value: str
    confidence: float
    evidence_refs: list[str]
    scope: str = "observed_example"
    generalization_status: str = "not_yet_general"


@dataclass
class Rule:
    rule_type: str
    subject_concept: str
    predicate: str
    object_value: str
    condition: dict[str, Any]
    exceptions: list[str]
    source_evidence_id: str
    confidence: float = 0.55
    status: str = "provisional"
    rule_id: str = field(default_factory=lambda: new_id("rule"))
    created_at: str = field(default_factory=now_iso)


@dataclass
class Relation:
    relation_type: str
    target_concept: str
    confidence: float
    evidence_refs: list[str]
    status: str = "candidate"


@dataclass
class Concept:
    name: str
    display_name: str | None = None
    concept_id: str = field(default_factory=lambda: new_id("concept"))
    status: str = "forming"
    maturity: str = "seed"
    confidence: float = 0.1
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    description: str = ""
    attributes: list[ConceptAttribute] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    open_questions: list[dict[str, str]] = field(default_factory=list)
    examples: list[dict[str, Any]] = field(default_factory=list)
    counterexamples: list[dict[str, Any]] = field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = now_iso()


@dataclass
class ExternalState:
    current_task: str
    visible_inputs: list[dict[str, Any]]
    conversation_context: list[dict[str, Any]]
    state_id: str = field(default_factory=lambda: new_id("external_state"))
    timestamp: str = field(default_factory=now_iso)


@dataclass
class InternalState:
    attention_focus: list[dict[str, Any]] = field(default_factory=list)
    pending_questions: list[dict[str, Any]] = field(default_factory=list)
    active_concepts: list[dict[str, Any]] = field(default_factory=list)
    conflict_set: list[dict[str, Any]] = field(default_factory=list)
    curiosity_queue: list[dict[str, Any]] = field(default_factory=list)
    identity_focus: list[str] = field(
        default_factory=lambda: [
            "learn_from_evidence",
            "avoid_encyclopedia_copying",
            "ask_when_uncertain",
        ]
    )
    sleep_status: dict[str, Any] = field(default_factory=lambda: {"state": "idle"})
    state_id: str = field(default_factory=lambda: new_id("internal_state"))
    timestamp: str = field(default_factory=now_iso)


def to_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value


def concept_from_dict(payload: dict[str, Any]) -> Concept:
    concept = Concept(
        name=payload["name"],
        display_name=payload.get("display_name"),
        concept_id=payload.get("concept_id", new_id("concept")),
        status=payload.get("status", "forming"),
        maturity=payload.get("maturity", "seed"),
        confidence=float(payload.get("confidence", 0.1)),
        created_at=payload.get("created_at", now_iso()),
        updated_at=payload.get("updated_at", now_iso()),
        description=payload.get("description", ""),
        evidence_refs=list(payload.get("evidence_refs", [])),
        open_questions=list(payload.get("open_questions", [])),
        examples=list(payload.get("examples", [])),
        counterexamples=list(payload.get("counterexamples", [])),
    )
    concept.attributes = [
        ConceptAttribute(
            name=item["name"],
            value=item["value"],
            confidence=float(item.get("confidence", 0.1)),
            evidence_refs=list(item.get("evidence_refs", [])),
            scope=item.get("scope", "observed_example"),
            generalization_status=item.get("generalization_status", "not_yet_general"),
        )
        for item in payload.get("attributes", [])
    ]
    concept.relations = [
        Relation(
            relation_type=item["relation_type"],
            target_concept=item["target_concept"],
            confidence=float(item.get("confidence", 0.1)),
            evidence_refs=list(item.get("evidence_refs", [])),
            status=item.get("status", "candidate"),
        )
        for item in payload.get("relations", [])
    ]
    return concept


def evidence_from_dict(payload: dict[str, Any]) -> Evidence:
    evidence = Evidence(
        evidence_id=payload.get("evidence_id", new_id("evidence")),
        claim=Claim(**payload["claim"]),
        source_type=payload["source_type"],
        source_identity=payload["source_identity"],
        refs=list(payload.get("refs", [])),
        status=payload.get("status", "provisional"),
        confidence=float(payload.get("confidence", 0.6)),
        timestamp=payload.get("timestamp", now_iso()),
        sample_id=payload.get("sample_id"),
    )
    evidence.validation_events = [
        ValidationEvent(
            event_type=item["event_type"],
            reason=item["reason"],
            previous_status=item["previous_status"],
            new_status=item["new_status"],
            timestamp=item.get("timestamp", now_iso()),
        )
        for item in payload.get("validation_events", [])
    ]
    return evidence


def rule_from_dict(payload: dict[str, Any]) -> Rule:
    return Rule(
        rule_id=payload.get("rule_id", new_id("rule")),
        rule_type=payload["rule_type"],
        subject_concept=payload["subject_concept"],
        predicate=payload["predicate"],
        object_value=payload["object_value"],
        condition=dict(payload.get("condition", {})),
        exceptions=list(payload.get("exceptions", [])),
        source_evidence_id=payload["source_evidence_id"],
        confidence=float(payload.get("confidence", 0.55)),
        status=payload.get("status", "provisional"),
        created_at=payload.get("created_at", now_iso()),
    )
