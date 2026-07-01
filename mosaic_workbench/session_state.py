from __future__ import annotations

from mosaic_agent.session_models import InteractiveSession


def select_concept(session: InteractiveSession, concept_id: str) -> InteractiveSession:
    if concept_id not in {concept.concept_id for concept in session.concepts}:
        raise ValueError(f"unknown concept ID: {concept_id}")
    return session.model_copy(update={"selected_concept_id": concept_id})
