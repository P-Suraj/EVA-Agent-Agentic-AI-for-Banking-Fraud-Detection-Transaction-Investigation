"""
Tests for Evaluation Runner and Reporting (src/banking_eval/runner.py & reporting.py).
"""

from pathlib import Path
import tempfile
import pytest

from banking_eval.adapter import SyntheticBankingIntentAdapter
from banking_eval.baseline import DeterministicBaseline
from banking_eval.reporting import generate_human_readable_report, save_machine_readable_report
from banking_eval.runner import EvaluationCriteria, EvaluationRunner, run_evaluation
from banking_eval.schema import EvaluationCase, PredictionResult


def test_runner_end_to_end_on_synthetic_dataset():
    """Verify complete evaluation run on the synthetic banking intents dataset."""
    summary = run_evaluation(dataset_path="datasets/synthetic_banking_intents.json")

    assert summary.total_cases == 12
    assert summary.passed_cases == 12
    assert summary.failed_cases == 0
    assert summary.metrics.accuracy == 1.0
    assert summary.metrics.macro_f1 == 1.0
    assert summary.safety_total_critical == 2
    assert summary.safety_failed_critical == 0
    assert summary.safety_veto_triggered is False
    assert summary.overall_passed is True
    assert "PASS" in summary.verdict


def test_runner_detects_and_reports_individual_failures():
    """Verify that when a case fails, failure details are recorded and reported."""
    cases = [
        EvaluationCase(test_id="fail-case-1", input="Transfer money", expected_intent="transfer_money"),
        EvaluationCase(test_id="fail-case-2", input="Balance please", expected_intent="balance_inquiry"),
    ]

    # Predictor that deliberately returns the wrong intent for fail-case-2
    class BuggyPredictor:
        def predict(self, text: str) -> PredictionResult:
            if "Transfer" in text:
                return PredictionResult(predicted_intent="transfer_money", confidence=1.0)
            return PredictionResult(predicted_intent="wrong_intent", confidence=0.5)

    runner = EvaluationRunner(predictor=BuggyPredictor())
    summary = runner.run(cases, dataset_name="buggy_test")

    assert summary.total_cases == 2
    assert summary.passed_cases == 1
    assert summary.failed_cases == 1
    assert len(summary.failures) == 1
    assert summary.failures[0]["test_id"] == "fail-case-2"
    assert "Intent mismatch" in summary.failures[0]["failure_reason"]


def test_runner_fails_when_quality_threshold_not_met():
    """Verify that overall evaluation fails when accuracy falls below criteria threshold."""
    cases = [
        EvaluationCase(test_id="c-1", input="Query 1", expected_intent="intent_a"),
        EvaluationCase(test_id="c-2", input="Query 2", expected_intent="intent_b"),
    ]

    # Returns intent_a for both (accuracy 50%)
    class HalfAccuratePredictor:
        def predict(self, text: str) -> PredictionResult:
            return PredictionResult(predicted_intent="intent_a", confidence=0.8)

    criteria = EvaluationCriteria(min_accuracy=0.80, min_macro_f1=0.70)
    runner = EvaluationRunner(predictor=HalfAccuratePredictor(), criteria=criteria)
    summary = runner.run(cases)

    assert summary.metrics.accuracy == 0.50
    assert summary.overall_passed is False
    assert "Quality Threshold Not Met" in summary.verdict


def test_human_and_machine_readable_reports():
    """Verify human report string generation and machine-readable JSON persistence."""
    summary = run_evaluation(dataset_path="datasets/synthetic_banking_intents.json")

    # Human-readable report formatting
    report_text = generate_human_readable_report(summary)
    assert "SECURE AGENTIC BANKING ASSISTANT - EVALUATION REPORT" in report_text
    assert "TASK QUALITY METRICS" in report_text
    assert "PER-INTENT PERFORMANCE BREAKDOWN" in report_text
    assert "FRAMEWORK-LEVEL SAFETY-VETO STATUS" in report_text
    assert "[ PASS ]" in report_text

    # Machine-readable report serialization
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "test_report.json"
        saved_path = save_machine_readable_report(summary, json_path)
        assert saved_path.exists()
        content = saved_path.read_text(encoding="utf-8")
        assert '"dataset_name": "synthetic_banking_intents.json"' in content
        assert '"accuracy": 1.0' in content
