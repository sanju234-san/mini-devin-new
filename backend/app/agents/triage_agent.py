"""Triage agent node for classifying incoming GitHub issues."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from app.agents.schemas import (
    EventType,
    ModelInfo,
    ModelKind,
    RunState,
    StepEvent,
    StopReason,
    TriageCategory,
    TriageResult,
)
from app.ml_models.triage_classifier import classify
from app.retrieval.query_transform import clean_issue_text


def triage_node(state: RunState) -> dict:
    """Classify the incoming issue text using the trained classifier."""
    raw_issue_text = state.get("issue_text", "")
    run_id = state.get("run_id", "")

    cleaned_query = clean_issue_text(raw_issue_text)

    try:
        category_str = classify(cleaned_query)
        category = TriageCategory(category_str)

        event = StepEvent(
            run_id=run_id,
            event_id=f"evt_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent="triage",
            step="triage",
            event_type=EventType.COMPLETED,
            model_info=ModelInfo(kind=ModelKind.CLASSIFIER, name="triage_classifier"),
            message=f"Triage classified issue as {category.value}",
        )

        return {
            "triage_result": TriageResult(
                category=category,
                confidence=0.95,
                cleaned_query=cleaned_query,
            ),
            "current_step": "triage",
            "latest_event": event,
        }

    except Exception:
        error_event = StepEvent(
            run_id=run_id,
            event_id=f"evt_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent="triage",
            step="triage",
            event_type=EventType.FAILED,
            model_info=ModelInfo(kind=ModelKind.CLASSIFIER, name="triage_classifier"),
            message="Triage classification failed",
        )
        return {
            "node_error": StopReason.ERROR,
            "current_step": "triage",
            "latest_event": error_event,
        }


# Alias for graph node registration
triage = triage_node
