from __future__ import annotations

from .concept_graph import ConceptGraph
from .models import new_id, now_iso


class CognitiveIntegrationEngine:
    """Runs the generic post-learning consolidation pass.

    This is the small "organize my mind" step after any evidence enters Athena.
    It keeps concept membership, boundaries and question states in sync without
    depending on a specific domain such as fruit.
    """

    def integrate(
        self,
        graph: ConceptGraph,
        *,
        evidence_statuses: dict[str, str],
        trigger: str,
    ) -> dict[str, object]:
        graph.apply_evidence_statuses(evidence_statuses)
        membership = graph.refresh_category_membership()
        question_resolution = graph.resolve_questions_by_relations()
        boundary_questions = graph.refresh_boundary_questions()

        return {
            "integration_report_id": new_id("cognitive_integration_report"),
            "timestamp": now_iso(),
            "trigger": trigger,
            "membership": membership,
            "question_resolution": question_resolution,
            "boundary_questions": boundary_questions,
        }
