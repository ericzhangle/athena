from __future__ import annotations

from .models import ExternalState, InternalState, Perception, new_id


class StateManager:
    """Maintains external and internal cognitive state for the prototype."""

    def create_external_state(
        self,
        *,
        current_task: str,
        user_text: str,
        image_path: str | None = None,
    ) -> ExternalState:
        visible_inputs = []
        if image_path:
            visible_inputs.append(
                {
                    "input_id": new_id("input"),
                    "type": "image",
                    "path": image_path,
                    "status": "available",
                }
            )

        return ExternalState(
            current_task=current_task,
            visible_inputs=visible_inputs,
            conversation_context=[
                {
                    "turn_id": new_id("turn"),
                    "speaker": "user",
                    "text": user_text,
                }
            ],
        )

    def create_initial_internal_state(
        self,
        *,
        candidate_concepts: list[str],
        relation_targets: list[str],
    ) -> InternalState:
        state = InternalState()

        for concept in candidate_concepts:
            state.attention_focus.append(
                {
                    "target": concept,
                    "reason": "new_concept_introduced_by_user",
                    "strength": 0.85,
                }
            )
            state.active_concepts.append(
                {
                    "name": concept,
                    "status": "forming",
                    "confidence": 0.25,
                    "evidence_refs": [],
                }
            )
            state.pending_questions.append(
                {
                    "question_id": new_id("question"),
                    "question": f"{concept} 是什么？你能给我一个具体例子吗？",
                    "reason": "new_concept_needs_direct_evidence",
                    "priority": 0.85,
                    "status": "open",
                }
            )

        for target in relation_targets:
            state.curiosity_queue.append(
                {
                    "topic": target,
                    "reason": "relation_target_concept_is_not_mature",
                    "priority": 0.8,
                }
            )
            state.pending_questions.append(
                {
                    "question_id": new_id("question"),
                    "question": f"{target} 是什么意思？它和刚才的新概念是什么关系？",
                    "reason": "relation_target_concept_is_not_mature",
                    "priority": 0.8,
                    "status": "open",
                }
            )

        return state

    def update_after_perception(
        self,
        state: InternalState,
        *,
        perception: Perception,
        candidate_concepts: list[str],
    ) -> InternalState:
        for concept in candidate_concepts:
            state.attention_focus.append(
                {
                    "target": f"perceptual_features_for_{concept}",
                    "reason": "new_perception_may_support_active_concept",
                    "strength": 0.9,
                }
            )
            state.pending_questions.append(
                {
                    "question_id": new_id("question"),
                    "question": f"这次观察到的特征是否真的属于 {concept}，还是只是这个例子的特征？",
                    "reason": "distinguish_instance_features_from_general_concept",
                    "priority": 0.75,
                    "status": "open",
                }
            )

        state.curiosity_queue.append(
            {
                "topic": "visual_generalization",
                "reason": f"{len(perception.features)} perceptual features are available but not generalized",
                "priority": 0.7,
            }
        )
        return state
