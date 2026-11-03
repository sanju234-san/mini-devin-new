"""Triage classifier loading and inference.

Loads the scikit-learn pipeline lazily on first prediction and caches it.
Provides cache reset helper for testing.
"""

from __future__ import annotations

import json
import logging
import os
import pickle
import re

logger = logging.getLogger(__name__)

VALID_CLASSES = frozenset({"bug_fix", "small_feature", "test_writing", "out_of_scope"})
MIN_CONFIDENCE = float(os.getenv("MINI_DEVIN_MIN_CONFIDENCE", "0.55"))
MIN_MARGIN = float(os.getenv("MINI_DEVIN_MIN_MARGIN", "0.12"))
TITLE_WEIGHT = int(os.getenv("MINI_DEVIN_TITLE_WEIGHT", "3"))
MAX_BODY_CHARS = int(os.getenv("MINI_DEVIN_TRIAGE_MAX_BODY_CHARS", "800"))

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
PIPELINE_PATH = os.path.join(ARTIFACTS_DIR, "triage_pipeline.joblib")
METADATA_PATH = os.path.join(ARTIFACTS_DIR, "triage_metadata.json")
DISTILBERT_DIR = os.path.join(ARTIFACTS_DIR, "distilbert_candidate")

_PIPELINE_CACHE = None
_METADATA_CACHE = None
_DISTILBERT_MODEL = None
_DISTILBERT_TOKENIZER = None


class TriageModelNotFound(Exception):
    """Raised when the triage model artifact or metadata file is missing."""


class TriagePredictionError(Exception):
    """Raised when the model prediction is invalid or unexpected."""


def reset_cache() -> None:
    """Reset the cached model pipeline, DistilBERT model, and metadata."""
    global _PIPELINE_CACHE, _METADATA_CACHE, _DISTILBERT_MODEL, _DISTILBERT_TOKENIZER
    _PIPELINE_CACHE = None
    _METADATA_CACHE = None
    _DISTILBERT_MODEL = None
    _DISTILBERT_TOKENIZER = None


LDA_TOPIC_MAPPING: dict[int, str] = {
    0: "small_feature",
    1: "bug_fix",
    2: "bug_fix",
    3: "out_of_scope",
    4: "out_of_scope",
}


_INTENT_TAG_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\[\s*(?:feature(?:\s+request)?|enhancement)\s*\]|^(?:feature(?:\s+request)?|enhancement)\s*:", re.IGNORECASE), "small_feature"),
    (re.compile(r"\[\s*(?:bug(?:\s+report)?|defect|fix)\s*\]|^(?:bug(?:\s+report)?|defect|fix)\s*:", re.IGNORECASE), "bug_fix"),
    (re.compile(r"\[\s*(?:test(?:s|\s+writing)?)\s*\]|^(?:test(?:s|\s+writing)?)\s*:", re.IGNORECASE), "test_writing"),
    (re.compile(r"\[\s*(?:question|discussion|rfc|out-of-scope|wontfix)\s*\]|^(?:question|discussion|rfc|out-of-scope|wontfix)\s*:", re.IGNORECASE), "out_of_scope"),
]


def extract_intent_tag(title: str, labels: list[str] | None = None) -> tuple[str | None, float]:
    """Extract explicit intent tag from issue title or labels."""
    if labels:
        for lbl in labels:
            lbl_lower = lbl.lower()
            if any(k in lbl_lower for k in ("feature", "enhancement")):
                return "small_feature", 0.95
            if any(k in lbl_lower for k in ("bug", "defect", "fix")):
                return "bug_fix", 0.95
            if "test" in lbl_lower:
                return "test_writing", 0.95

    clean_t = title.strip()
    for pattern, category in _INTENT_TAG_PATTERNS:
        if pattern.search(clean_t):
            return category, 0.95

    return None, 0.0


def preprocess_triage_text(
    title: str,
    body: str = "",
    title_weight: int = TITLE_WEIGHT,
    max_body_chars: int = MAX_BODY_CHARS,
) -> str:
    """Sanitize body text, truncate, and emphasize title via repetition."""
    cleaned_b = re.sub(r"```[\s\S]*?(?:```|$)", " ", body)
    cleaned_b = re.sub(r"(?:Traceback \(most recent call last\):|File \".*?\", line \d+.*).*", " ", cleaned_b)
    cleaned_b = re.sub(r"https?://\S+", " ", cleaned_b)
    cleaned_b = re.sub(r"^[ \t]*[-*][ \t]*\[[ xX]\][ \t]*", " ", cleaned_b, flags=re.MULTILINE)
    cleaned_b = re.sub(r"^[ \t]*#{1,6}[^\n]*", " ", cleaned_b, flags=re.MULTILINE)
    cleaned_b = re.sub(r"\s+", " ", cleaned_b).strip()[:max_body_chars]

    weighted_title = " ".join([title.strip()] * max(1, title_weight))
    return f"{weighted_title} {cleaned_b}".strip()


class _DummyRandomState:
    """Stub to handle cross-version unpickling of NumPy 2.x RandomState in NumPy 1.x."""
    def __init__(self, *args, **kwargs):
        pass
    def __setstate__(self, state):
        pass


class _CompatUnpickler(pickle.Unpickler):
    """Custom unpickler that safely handles BitGenerator changes across NumPy versions."""
    def find_class(self, module: str, name: str):
        if module == "numpy.random._pickle" and name in ("__randomstate_ctor", "__bit_generator_ctor"):
            return lambda *args, **kwargs: _DummyRandomState()
        return super().find_class(module, name)


def load_pipeline(
    pipeline_path: str | None = None,
    metadata_path: str | None = None,
):
    """Load and cache the triage pipeline and metadata.

    Supports both supervised classifiers and unsupervised LDA topic models.
    """
    global _PIPELINE_CACHE, _METADATA_CACHE
    if _PIPELINE_CACHE is not None:
        return _PIPELINE_CACHE

    if pipeline_path is not None:
        pipe_file = pipeline_path
    elif PIPELINE_PATH != os.path.join(ARTIFACTS_DIR, "triage_pipeline.joblib"):
        pipe_file = PIPELINE_PATH
    else:
        lda_clean = os.path.join(ARTIFACTS_DIR, "triage_pipeline_lda.joblib")
        lda_pkl = os.path.join(ARTIFACTS_DIR, "pipeline.pkl")
        if os.path.exists(lda_clean):
            pipe_file = lda_clean
        elif os.path.exists(lda_pkl):
            pipe_file = lda_pkl
        else:
            pipe_file = PIPELINE_PATH

    meta_file = metadata_path if metadata_path is not None else METADATA_PATH

    if not os.path.exists(pipe_file):
        raise TriageModelNotFound(
            f"Triage model pipeline not found at {pipe_file}. "
            f"Train the model first using train_triage.py."
        )

    if not os.path.exists(meta_file):
        raise TriageModelNotFound(
            f"Triage model metadata not found at {meta_file}. "
            f"Train the model first using train_triage.py."
        )

    import joblib

    try:
        pipeline = joblib.load(pipe_file)
    except Exception:
        # Fall back to compatibility unpickler for Colab-exported pickle files
        try:
            with open(pipe_file, "rb") as f:
                pipeline = _CompatUnpickler(f).load()
        except Exception as e:
            raise TriageModelNotFound(f"Failed to load triage pipeline: {e}") from e

    with open(meta_file, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    _PIPELINE_CACHE = pipeline
    _METADATA_CACHE = metadata
    return _PIPELINE_CACHE


def classify(issue_text: str) -> str:
    """Return one of: 'bug_fix', 'small_feature', 'test_writing', 'out_of_scope'."""
    category, _ = classify_with_confidence(issue_text)
    return category
 
 
def load_distilbert(model_dir: str | None = None):
    """Load and cache the fine-tuned DistilBERT model and tokenizer."""
    global _DISTILBERT_MODEL, _DISTILBERT_TOKENIZER
    if _DISTILBERT_MODEL is not None and _DISTILBERT_TOKENIZER is not None:
        return _DISTILBERT_MODEL, _DISTILBERT_TOKENIZER

    target_dir = model_dir if model_dir is not None else DISTILBERT_DIR
    if not os.path.exists(target_dir):
        raise TriageModelNotFound(f"DistilBERT candidate directory not found at {target_dir}")

    try:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(target_dir)
        model = AutoModelForSequenceClassification.from_pretrained(target_dir)
        model.eval()
        _DISTILBERT_MODEL = model
        _DISTILBERT_TOKENIZER = tokenizer
        return _DISTILBERT_MODEL, _DISTILBERT_TOKENIZER
    except Exception as exc:
        raise TriageModelNotFound(f"Failed to load DistilBERT model: {exc}") from exc


def classify_with_distilbert(issue_text: str) -> tuple[str, float]:
    """Classify issue using the fine-tuned DistilBERT candidate."""
    import torch
    model, tokenizer = load_distilbert()
    inputs = tokenizer(issue_text, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)[0].tolist()

    id2label = getattr(model.config, "id2label", None) or {
        0: "bug_fix", 1: "small_feature", 2: "test_writing", 3: "out_of_scope"
    }
    best_idx = int(max(range(len(probs)), key=lambda i: probs[i]))
    raw_label = id2label.get(best_idx, str(best_idx))
    category = raw_label if raw_label in VALID_CLASSES else "out_of_scope"
    confidence = float(probs[best_idx])
    return category, confidence


def classify_with_confidence(issue_text: str) -> tuple[str, float]:
    """Return tuple of (label, confidence) using active classifier."""
    if os.environ.get("MINI_DEVIN_TRIAGE_MODEL", "").lower() == "distilbert":
        try:
            return classify_with_distilbert(issue_text)
        except Exception:
            pass  # Fall back to calibrated baseline pipeline

    pipeline = load_pipeline()

    # 1. Unsupervised LDA Topic Modeling Pipeline
    if hasattr(pipeline, "named_steps") and "lda" in pipeline.named_steps:
        theta = pipeline.transform([issue_text])[0]

        # Aggregate probability mass by label
        label_probs: dict[str, float] = {cls_name: 0.0 for cls_name in VALID_CLASSES}
        for topic_idx, prob in enumerate(theta):
            target_label = LDA_TOPIC_MAPPING.get(topic_idx, "out_of_scope")
            label_probs[target_label] += float(prob)

        sorted_labels = sorted(label_probs.items(), key=lambda x: x[1], reverse=True)
        top1_label, top1 = sorted_labels[0]
        top2_label, top2 = sorted_labels[1]
        margin = top1 - top2

        logger.info(
            "LDA Triage | theta=%s | top1=(%s, %.3f) | top2=(%s, %.3f) | margin=%.3f",
            [round(float(x), 3) for x in theta],
            top1_label,
            top1,
            top2_label,
            top2,
            margin,
        )

        # Margin-based rule: if strong margin or exceeds MIN_CONFIDENCE, keep top1
        if top1 >= MIN_CONFIDENCE or (top1 >= 0.35 and margin >= MIN_MARGIN):
            return top1_label, top1
        return top1_label, top1

    # 2. Supervised pipeline with predict_proba
    if hasattr(pipeline, "predict_proba"):
        probas = pipeline.predict_proba([issue_text])
        if len(probas) == 0 or len(probas[0]) == 0:
            raise TriagePredictionError("Triage pipeline returned empty probabilities.")
        proba = probas[0]
        if hasattr(pipeline, "classes_"):
            classes = list(pipeline.classes_)
            best_idx = int(max(range(len(proba)), key=lambda i: proba[i]))
            category = str(classes[best_idx])
            confidence = float(proba[best_idx])
        else:
            predictions = pipeline.predict([issue_text])
            category = str(predictions[0])
            confidence = float(max(proba))
    else:
        predictions = pipeline.predict([issue_text])
        category = str(predictions[0])
        confidence = 1.0

    if category not in VALID_CLASSES:
        raise TriagePredictionError(
            f"Triage pipeline returned unexpected class '{category}'. "
            f"Expected one of: {sorted(VALID_CLASSES)}."
        )

    return category, confidence
