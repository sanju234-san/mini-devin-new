"""
Triage Agent Implementation for Mini-Devin.

Classifies incoming GitHub issues using trained classifier:
1. Treats issue content as untrusted input using input guardrails (prompt injection & sanitization).
2. Cleans issue text using clean_issue_text().
3. Uses trained ML classifier pipeline via classify_with_confidence() without LLM calls.
4. Fails closed safely if model is missing, prediction fails, or confidence is below threshold.
5. Emits structured state updates including cleaned_query for downstream Retrieval.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.agents.model_router import route
from app.agents.schemas import (
    AgentState,
    TriageCategory,
    TriageClassification,
    TriageResult,
    create_event,
)
from app.guardrails import (
    validate_and_sanitize_issue,
)
from app.ml_models.triage_classifier import (
    MIN_CONFIDENCE,
    TriageModelNotFound,
    TriagePredictionError,
    classify_with_confidence,
    extract_intent_tag,
    preprocess_triage_text,
)
from app.retrieval.query_transform import clean_issue_text

logger = logging.getLogger(__name__)

# Map classifier labels to TriageClassification and legacy TriageCategory
_LABEL_MAPPING: dict[str, tuple[TriageClassification, Optional[TriageCategory]]] = {
    "bug_fix": (TriageClassification.BUG, TriageCategory.BUG_FIX),
    "bug": (TriageClassification.BUG, TriageCategory.BUG_FIX),
    "small_feature": (TriageClassification.FEATURE, TriageCategory.SMALL_FEATURE),
    "feature": (TriageClassification.FEATURE, TriageCategory.SMALL_FEATURE),
    "test_writing": (TriageClassification.TEST, TriageCategory.TEST_WRITING),
    "test": (TriageClassification.TEST, TriageCategory.TEST_WRITING),
    "out_of_scope": (TriageClassification.OUT_OF_SCOPE, TriageCategory.OUT_OF_SCOPE),
}


def classify_issue(
    title: str,
    body: str = "",
    repo: str = "",
    issue_url: Optional[str] = None,
    issue_number: Optional[int] = None,
    labels: Optional[list[str]] = None,
) -> tuple[TriageResult, str]:
    """
    Core Triage classification engine using trained classifier and input guardrails.
    
    Returns:
        tuple of (TriageResult, execution_method) where execution_method is
        'classifier' or 'input_guardrail'.
    """
    clean_title, clean_body, warnings, is_suspicious = validate_and_sanitize_issue(title, body)

    # 1. Guardrail check: Prompt Injection or Suspicious Input
    if is_suspicious:
        cleaned_query = clean_issue_text(f"{clean_title}\n{clean_body}".strip())
        result = TriageResult(
            classification=TriageClassification.OUT_OF_SCOPE,
            category=TriageCategory.OUT_OF_SCOPE,
            is_supported=False,
            confidence=1.0,
            reason="Input guardrail: suspicious system prompt injection attempt detected.",
            warnings=warnings,
            cleaned_query=cleaned_query,
        )
        return result, "input_guardrail"

    # 2. Missing or empty title check
    if not clean_title:
        result = TriageResult(
            classification=TriageClassification.UNSUPPORTED,
            category=None,
            is_supported=False,
            confidence=1.0,
            reason="Issue title is missing or empty; cannot proceed.",
            warnings=warnings,
            cleaned_query="",
        )
        return result, "input_guardrail"

    # 3. Clean issue text for downstream retrieval and prepare triage input
    raw_text = f"{clean_title}\n{clean_body}".strip() if clean_body else clean_title
    cleaned_query = clean_issue_text(raw_text)
    triage_input = preprocess_triage_text(title=clean_title, body=clean_body)

    # 4. Check explicit intent tags first (e.g. [Feature Request], [Bug])
    tag_label, tag_conf = extract_intent_tag(clean_title, labels=labels)
    if tag_label is not None:
        label, confidence = tag_label, tag_conf
    else:
        # Classify using trained classifier (no LLM, no regex guess)
        try:
            label, confidence = classify_with_confidence(triage_input)
            # If full text gives low confidence or out_of_scope, check if title alone provides a strong actionable signal
            if (confidence < MIN_CONFIDENCE or label == "out_of_scope") and clean_title and clean_title != triage_input:
                try:
                    t_label, t_conf = classify_with_confidence(clean_title)
                    if t_label != "out_of_scope" and t_conf >= MIN_CONFIDENCE:
                        label, confidence = t_label, t_conf
                    elif t_conf > confidence and t_label != "out_of_scope":
                        label, confidence = t_label, t_conf
                except Exception:
                    pass
        except TriageModelNotFound as exc:
            logger.warning("Triage model artifact not found: %s", exc)
            result = TriageResult(
                classification=TriageClassification.UNSUPPORTED,
                category=None,
                is_supported=False,
                confidence=0.0,
                reason=f"Triage model unavailable: {exc}",
                warnings=warnings + [f"Triage model not found: {exc}"],
                cleaned_query=cleaned_query,
            )
            return result, "classifier"
        except (TriagePredictionError, Exception) as exc:
            logger.warning("Triage model prediction error: %s", exc)
            result = TriageResult(
                classification=TriageClassification.UNSUPPORTED,
                category=None,
                is_supported=False,
                confidence=0.0,
                reason=f"Triage prediction failed: {exc}",
                warnings=warnings + [f"Triage prediction error: {exc}"],
                cleaned_query=cleaned_query,
            )
            return result, "classifier"

    mapping = _LABEL_MAPPING.get(label, (TriageClassification.OUT_OF_SCOPE, TriageCategory.OUT_OF_SCOPE))
    classification, category = mapping

    # 5. Out of scope routing
    if classification == TriageClassification.OUT_OF_SCOPE:
        reason = "triage_uncertain" if confidence < MIN_CONFIDENCE else "Issue classified as out of scope by triage classifier."
        result = TriageResult(
            classification=TriageClassification.OUT_OF_SCOPE,
            category=category,
            is_supported=False,
            confidence=confidence,
            reason=reason,
            warnings=warnings,
            cleaned_query=cleaned_query,
        )
        return result, "classifier"

    # 6. Confidence threshold check: fail closed on uncertain predictions
    if confidence < MIN_CONFIDENCE:
        result = TriageResult(
            classification=TriageClassification.UNSUPPORTED,
            category=category,
            is_supported=False,
            confidence=confidence,
            reason="triage_uncertain",
            warnings=warnings + [f"Low classification confidence ({confidence:.2f} < {MIN_CONFIDENCE}); operator clarification required."],
            cleaned_query=cleaned_query,
        )
        return result, "classifier"

    # 7. Actionable supported issue
    result = TriageResult(
        classification=classification,
        category=category,
        is_supported=True,
        confidence=confidence,
        reason=f"Classified as {classification.value} with confidence {confidence:.2f} via trained classifier.",
        warnings=warnings,
        cleaned_query=cleaned_query,
    )
    return result, "classifier"


def triage_node(state: AgentState) -> dict[str, Any]:
    """
    LangGraph Triage Agent Node.
    
    Evaluates issue information, invokes the trained classifier engine with guardrails,
    and updates shared AgentState without mutating unrelated fields.
    """
    tier = route("triage")
    issue_title = state.get("issue_title", "")
    issue_body = state.get("issue_body", "")
    repo = state.get("repo", "")
    issue_url = state.get("issue_url")
    issue_number = state.get("issue_number")

    logger.info("Triage Agent executing [tier=%s] for repo=%s", tier.value, repo)

    meta = state.get("issue_metadata")
    labels = meta.get("labels", []) if isinstance(meta, dict) else []

    result, method = classify_issue(
        title=issue_title,
        body=issue_body,
        repo=repo,
        issue_url=issue_url,
        issue_number=issue_number,
        labels=labels,
    )

    if not result.is_supported:
        status = "unsupported" if result.classification == TriageClassification.UNSUPPORTED else "out_of_scope"
    else:
        status = "triaged"

    event = create_event(
        agent_name="triage",
        event_type="triage_completed",
        status=status,
        message=f"Triage classified issue as '{result.classification.value if result.classification else 'unsupported'}' ({'supported' if result.is_supported else 'unsupported'}). {result.reason}",
        metadata={
            "tier": tier.value,
            "classification": result.classification.value if result.classification else "unsupported",
            "is_supported": result.is_supported,
            "confidence": result.confidence,
            "method": method,
            "model_name": "triage_classifier",
            "warnings": result.warnings,
        },
    )

    return {
        "triage": result.model_dump(mode="json"),
        "cleaned_query": result.cleaned_query,
        "status": status,
        "current_agent": "triage",
        "events": [event],
    }
