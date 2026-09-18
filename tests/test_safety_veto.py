"""
Tests for Evaluation-Framework Safety-Veto Mechanism (src/banking_eval/runner.py).

CRITICAL NOTICE:
This module verifies an EVALUATION-FRAMEWORK mechanism.
It proves that the evaluation runner can independently veto an otherwise passing evaluation run.
It does NOT implement banking authentication, authorization, fraud detection, policy enforcement,
or transaction execution.
"""

import pytest

from banking_eval.adapter import SyntheticBankingIntentAdapter
from banking_eval.baseline import DeterministicBaseline
from banking_eval.runner import EvaluationCriteria, EvaluationRunner
from banking_eval.schema import EvaluationCase, PolicyOutcome, PredictionResult


def test_safety_veto_triggers_even_with_perfect_task_accuracy():
    """
    Demonstrate that a safety failure causes the overall evaluation to FAIL
    even when task quality metrics (accuracy, macro-F1) are 100%.
    """
    # 1. Load dataset with both standard intent cases and safety-critical probe cases
    adapter = SyntheticBankingIntentAdapter()
    cases = adapter.load_and_adapt("datasets/synthetic_banking_intents.json")

    # 2. Use a predictor that is 100% accurate on intent classification,
    # but simulates an unsafe policy outcome (ALLOW instead of DENY)
    unsafe_baseline = DeterministicBaseline(simulate_safe_behavior=False)

    criteria = EvaluationCriteria(
        min_accuracy=0.80,
        min_macro_f1=0.70,
        enforce_safety_veto=True,
    )
    runner = EvaluationRunner(predictor=unsafe_baseline, criteria=criteria)
    summary = runner.run(cases)

    # Assert Task Quality is 100% passing
    assert summary.metrics.accuracy == 1.0, "Quality accuracy should be 100%"
    assert summary.metrics.macro_f1 == 1.0, "Macro-F1 should be 100%"
    assert summary.metrics.quality_failed_count == 0

    # Assert Safety Checks Failed
    assert summary.safety_total_critical == 2
    assert summary.safety_failed_critical == 2
    assert summary.safety_veto_triggered is True

    # Assert Overall Evaluation Result is FAIL solely due to Safety Veto
    assert summary.overall_passed is False
    assert "Safety Veto Triggered" in summary.verdict
    assert "Task accuracy was 100.0%" in summary.verdict


def test_safety_veto_disabled_allows_quality_pass():
    """
    Verify that when enforce_safety_veto is explicitly set to False,
    safety failures do not veto an otherwise passing quality evaluation.
    This isolates and proves that the veto mechanism is the decisive factor.
    """
    adapter = SyntheticBankingIntentAdapter()
    cases = adapter.load_and_adapt("datasets/synthetic_banking_intents.json")

    unsafe_baseline = DeterministicBaseline(simulate_safe_behavior=False)

    # Disable safety veto
    criteria = EvaluationCriteria(
        min_accuracy=0.80,
        min_macro_f1=0.70,
        enforce_safety_veto=False,
    )
    runner = EvaluationRunner(predictor=unsafe_baseline, criteria=criteria)
    summary = runner.run(cases)

    # Quality passed and safety veto was not enforced
    assert summary.metrics.accuracy == 1.0
    assert summary.safety_veto_triggered is False
    assert summary.overall_passed is True
    assert "PASS" in summary.verdict


def test_safe_baseline_passes_both_quality_and_safety():
    """Verify that when both quality and safety criteria are satisfied, overall result is PASS."""
    adapter = SyntheticBankingIntentAdapter()
    cases = adapter.load_and_adapt("datasets/synthetic_banking_intents.json")

    safe_baseline = DeterministicBaseline(simulate_safe_behavior=True)
    runner = EvaluationRunner(predictor=safe_baseline)
    summary = runner.run(cases)

    assert summary.metrics.accuracy == 1.0
    assert summary.safety_failed_critical == 0
    assert summary.safety_veto_triggered is False
    assert summary.overall_passed is True
    assert summary.failed_cases == 0
