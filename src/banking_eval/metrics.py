"""
Deterministic Metrics Calculation Module.

Pure-Python calculation of evaluation metrics:
- Overall accuracy
- Per-intent Precision, Recall, F1, and Support
- Macro-averaged Precision, Recall, and Macro-F1

No external ML dependencies (no scikit-learn, numpy, etc.).
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from banking_eval.schema import CaseEvaluationResult


class IntentMetric(BaseModel):
    """Metrics for an individual intent class."""
    model_config = ConfigDict(extra="forbid")

    intent: str
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)
    f1_score: float = Field(ge=0.0, le=1.0)
    support: int = Field(ge=0)
    true_positives: int = Field(ge=0)
    false_positives: int = Field(ge=0)
    false_negatives: int = Field(ge=0)


class EvaluationMetrics(BaseModel):
    """Aggregate evaluation metrics."""
    model_config = ConfigDict(extra="forbid")

    total_evaluated: int = Field(ge=0)
    quality_passed_count: int = Field(ge=0)
    quality_failed_count: int = Field(ge=0)
    accuracy: float = Field(ge=0.0, le=1.0)
    macro_precision: float = Field(ge=0.0, le=1.0)
    macro_recall: float = Field(ge=0.0, le=1.0)
    macro_f1: float = Field(ge=0.0, le=1.0)
    per_intent: dict[str, IntentMetric] = Field(default_factory=dict)


def calculate_metrics(results: list[CaseEvaluationResult]) -> EvaluationMetrics:
    """
    Calculate accuracy, Macro-F1, and per-intent breakdown from case evaluation results.

    Only cases with an expected_intent are evaluated for intent metrics.
    """
    intent_cases = [r for r in results if r.case.expected_intent is not None]

    total_count = len(intent_cases)
    if total_count == 0:
        return EvaluationMetrics(
            total_evaluated=0,
            quality_passed_count=0,
            quality_failed_count=0,
            accuracy=0.0,
            macro_precision=0.0,
            macro_recall=0.0,
            macro_f1=0.0,
            per_intent={},
        )

    # 1. Overall Intent Accuracy
    correct_count = sum(1 for r in intent_cases if r.quality_passed)
    accuracy = correct_count / total_count

    # 2. Collect all unique classes present in ground truth or predictions
    all_classes = sorted(
        list(
            {r.case.expected_intent for r in intent_cases if r.case.expected_intent}
            | {r.prediction.predicted_intent for r in intent_cases if r.prediction.predicted_intent}
        )
    )

    per_intent: dict[str, IntentMetric] = {}
    f1_scores: list[float] = []
    precisions: list[float] = []
    recalls: list[float] = []

    # Calculate per-intent confusion components
    for cls in all_classes:
        tp = sum(
            1
            for r in intent_cases
            if r.case.expected_intent == cls and r.prediction.predicted_intent == cls
        )
        fp = sum(
            1
            for r in intent_cases
            if r.case.expected_intent != cls and r.prediction.predicted_intent == cls
        )
        fn = sum(
            1
            for r in intent_cases
            if r.case.expected_intent == cls and r.prediction.predicted_intent != cls
        )
        support = sum(1 for r in intent_cases if r.case.expected_intent == cls)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        # Only classes present in ground truth contribute to Macro averages
        if support > 0:
            precisions.append(precision)
            recalls.append(recall)
            f1_scores.append(f1)

        per_intent[cls] = IntentMetric(
            intent=cls,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            support=support,
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
        )

    macro_prec = sum(precisions) / len(precisions) if precisions else 0.0
    macro_rec = sum(recalls) / len(recalls) if recalls else 0.0
    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0

    return EvaluationMetrics(
        total_evaluated=total_count,
        quality_passed_count=correct_count,
        quality_failed_count=total_count - correct_count,
        accuracy=round(accuracy, 4),
        macro_precision=round(macro_prec, 4),
        macro_recall=round(macro_rec, 4),
        macro_f1=round(macro_f1, 4),
        per_intent=per_intent,
    )
