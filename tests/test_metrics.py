"""
Tests for Metrics Calculation (src/banking_eval/metrics.py).
"""

import pytest
from banking_eval.metrics import calculate_metrics
from banking_eval.schema import CaseEvaluationResult, EvaluationCase, PredictionResult


def _build_result(test_id: str, expected: str, predicted: str) -> CaseEvaluationResult:
    case = EvaluationCase(test_id=test_id, input="dummy text", expected_intent=expected)
    pred = PredictionResult(predicted_intent=predicted, confidence=1.0)
    passed = expected == predicted
    return CaseEvaluationResult(
        case=case,
        prediction=pred,
        passed=passed,
        quality_passed=passed,
        safety_passed=True,
        failure_reason=None if passed else f"mismatch: {expected} != {predicted}",
    )


def test_metrics_analytical_precision_recall_f1():
    """
    Test metrics calculation against a known confusion matrix:

    Dataset: 4 cases
    - Case 1: expected='A', predicted='A'  (TP for A)
    - Case 2: expected='A', predicted='B'  (FN for A, FP for B)
    - Case 3: expected='B', predicted='B'  (TP for B)
    - Case 4: expected='B', predicted='B'  (TP for B)

    Class A:
      TP = 1, FP = 0, FN = 1, Support = 2
      Precision = 1 / (1 + 0) = 1.0
      Recall = 1 / (1 + 1) = 0.5
      F1 = 2 * (1.0 * 0.5) / (1.0 + 0.5) = 2/3 = 0.6667

    Class B:
      TP = 2, FP = 1, FN = 0, Support = 2
      Precision = 2 / (2 + 1) = 2/3 = 0.6667
      Recall = 2 / (2 + 0) = 1.0
      F1 = 2 * (0.6667 * 1.0) / (0.6667 + 1.0) = 0.8000

    Overall:
      Total = 4
      Accuracy = 3 / 4 = 0.7500
      Macro-Precision = (1.0 + 0.6667) / 2 = 0.8333
      Macro-Recall = (0.5 + 1.0) / 2 = 0.7500
      Macro-F1 = (0.6667 + 0.8000) / 2 = 0.7333
    """
    results = [
        _build_result("1", "A", "A"),
        _build_result("2", "A", "B"),
        _build_result("3", "B", "B"),
        _build_result("4", "B", "B"),
    ]

    metrics = calculate_metrics(results)

    assert metrics.total_evaluated == 4
    assert metrics.quality_passed_count == 3
    assert metrics.quality_failed_count == 1
    assert metrics.accuracy == 0.75
    assert metrics.macro_precision == pytest.approx(0.8333, abs=1e-4)
    assert metrics.macro_recall == pytest.approx(0.7500, abs=1e-4)
    assert metrics.macro_f1 == pytest.approx(0.7333, abs=1e-4)

    # Class A
    assert metrics.per_intent["A"].precision == 1.0
    assert metrics.per_intent["A"].recall == 0.5
    assert metrics.per_intent["A"].f1_score == pytest.approx(0.6667, abs=1e-4)
    assert metrics.per_intent["A"].support == 2

    # Class B
    assert metrics.per_intent["B"].precision == pytest.approx(0.6667, abs=1e-4)
    assert metrics.per_intent["B"].recall == 1.0
    assert metrics.per_intent["B"].f1_score == 0.8
    assert metrics.per_intent["B"].support == 2


def test_metrics_empty_results():
    """Verify empty results produce zeros without division by zero."""
    metrics = calculate_metrics([])
    assert metrics.total_evaluated == 0
    assert metrics.accuracy == 0.0
    assert metrics.macro_f1 == 0.0
    assert len(metrics.per_intent) == 0


def test_metrics_skips_cases_without_expected_intent():
    """Verify that cases without an expected_intent are ignored for intent metrics."""
    case_no_intent = EvaluationCase(test_id="no-intent-1", input="Random text")
    pred = PredictionResult(predicted_intent="something")
    res = CaseEvaluationResult(
        case=case_no_intent,
        prediction=pred,
        passed=True,
        quality_passed=True,
        safety_passed=True,
    )
    metrics = calculate_metrics([res])
    assert metrics.total_evaluated == 0
