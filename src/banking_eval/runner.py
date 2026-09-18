"""
Evaluation Runner for Phase 0 Evaluation Foundation.

Executes test cases against a deterministic predictor, computes metrics,
enforces the framework-level safety veto, and compiles evaluation summaries.

NOTE: This is an evaluation framework mechanism for test verification.
It does NOT execute or enforce banking authorization or transactions.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol
from pydantic import BaseModel, ConfigDict, Field

from banking_eval.adapter import SyntheticBankingIntentAdapter
from banking_eval.baseline import DeterministicBaseline
from banking_eval.metrics import EvaluationMetrics, calculate_metrics
from banking_eval.schema import CaseEvaluationResult, EvaluationCase, PredictionResult


class PredictorProtocol(Protocol):
    """Protocol for any predictor or classifier used in evaluation."""
    def predict(self, text: str) -> PredictionResult:
        ...


class EvaluationCriteria(BaseModel):
    """Configurable acceptance criteria for the evaluation run."""
    model_config = ConfigDict(extra="forbid")

    min_accuracy: float = Field(default=0.80, ge=0.0, le=1.0)
    min_macro_f1: float = Field(default=0.70, ge=0.0, le=1.0)
    enforce_safety_veto: bool = Field(default=True)


class EvaluationSummary(BaseModel):
    """
    Comprehensive evaluation summary containing metrics, failure details,
    safety-veto status, and final pass/fail verdict.
    """
    model_config = ConfigDict(extra="forbid")

    timestamp: str
    dataset_name: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    metrics: EvaluationMetrics
    criteria: EvaluationCriteria
    safety_total_critical: int
    safety_passed_critical: int
    safety_failed_critical: int
    safety_veto_triggered: bool
    overall_passed: bool
    verdict: str
    failures: list[dict[str, Any]]
    case_results: list[CaseEvaluationResult]


class EvaluationRunner:
    """
    Orchestrates the evaluation pipeline.
    """

    def __init__(
        self,
        predictor: Optional[PredictorProtocol] = None,
        criteria: Optional[EvaluationCriteria] = None,
    ):
        self.predictor = predictor or DeterministicBaseline()
        self.criteria = criteria or EvaluationCriteria()

    def evaluate_case(self, case: EvaluationCase) -> CaseEvaluationResult:
        """Evaluate a single test case against the predictor."""
        prediction = self.predictor.predict(case.input)

        failure_reasons: list[str] = []

        # 1. Quality evaluation (Intent matching)
        quality_passed = True
        if case.expected_intent is not None:
            if prediction.predicted_intent != case.expected_intent:
                quality_passed = False
                failure_reasons.append(
                    f"Intent mismatch: expected '{case.expected_intent}', got '{prediction.predicted_intent}'"
                )

        # 2. Safety evaluation (Synthetic framework-level policy check)
        safety_passed = True
        if case.is_safety_critical:
            if case.expected_policy_outcome is not None:
                if prediction.predicted_policy_outcome != case.expected_policy_outcome:
                    safety_passed = False
                    failure_reasons.append(
                        f"Safety violation: expected simulated policy '{case.expected_policy_outcome}', "
                        f"got '{prediction.predicted_policy_outcome}'"
                    )

        passed = quality_passed and safety_passed
        reason = "; ".join(failure_reasons) if failure_reasons else None

        return CaseEvaluationResult(
            case=case,
            prediction=prediction,
            passed=passed,
            quality_passed=quality_passed,
            safety_passed=safety_passed,
            failure_reason=reason,
        )

    def run(
        self,
        cases: list[EvaluationCase],
        dataset_name: str = "synthetic_banking_intents",
    ) -> EvaluationSummary:
        """
        Run complete evaluation over a collection of cases.
        """
        case_results = [self.evaluate_case(case) for case in cases]
        metrics = calculate_metrics(case_results)

        total_cases = len(cases)
        passed_cases = sum(1 for r in case_results if r.passed)
        failed_cases = total_cases - passed_cases

        # Safety-veto checks
        safety_cases = [r for r in case_results if r.case.is_safety_critical]
        safety_total = len(safety_cases)
        safety_failed = sum(1 for r in safety_cases if not r.safety_passed)
        safety_passed = safety_total - safety_failed

        safety_veto_triggered = False
        if self.criteria.enforce_safety_veto and safety_failed > 0:
            safety_veto_triggered = True

        # Quality threshold checks
        quality_threshold_met = (
            metrics.accuracy >= self.criteria.min_accuracy
            and metrics.macro_f1 >= self.criteria.min_macro_f1
        )

        # Overall verdict determination
        if safety_veto_triggered:
            overall_passed = False
            verdict = (
                f"FAIL (Safety Veto Triggered: {safety_failed}/{safety_total} safety checks failed. "
                f"Task accuracy was {metrics.accuracy:.1%}, but evaluation is rejected by safety veto.)"
            )
        elif not quality_threshold_met:
            overall_passed = False
            verdict = (
                f"FAIL (Quality Threshold Not Met: Accuracy {metrics.accuracy:.1%} < {self.criteria.min_accuracy:.1%} "
                f"or Macro-F1 {metrics.macro_f1:.1%} < {self.criteria.min_macro_f1:.1%})"
            )
        else:
            overall_passed = True
            verdict = "PASS (All Quality & Safety Acceptance Criteria Satisfied)"

        # Collect failure details for reporting
        failures = []
        for r in case_results:
            if not r.passed:
                failures.append({
                    "test_id": r.case.test_id,
                    "category": str(r.case.category),
                    "input": r.case.input,
                    "expected_intent": r.case.expected_intent,
                    "predicted_intent": r.prediction.predicted_intent,
                    "expected_policy": str(r.case.expected_policy_outcome) if r.case.expected_policy_outcome else None,
                    "predicted_policy": str(r.prediction.predicted_policy_outcome) if r.prediction.predicted_policy_outcome else None,
                    "is_safety_critical": r.case.is_safety_critical,
                    "failure_reason": r.failure_reason,
                })

        return EvaluationSummary(
            timestamp=datetime.now(timezone.utc).isoformat(),
            dataset_name=dataset_name,
            total_cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            metrics=metrics,
            criteria=self.criteria,
            safety_total_critical=safety_total,
            safety_passed_critical=safety_passed,
            safety_failed_critical=safety_failed,
            safety_veto_triggered=safety_veto_triggered,
            overall_passed=overall_passed,
            verdict=verdict,
            failures=failures,
            case_results=case_results,
        )


def run_evaluation(
    dataset_path: str | Path = "datasets/synthetic_banking_intents.json",
    predictor: Optional[PredictorProtocol] = None,
    criteria: Optional[EvaluationCriteria] = None,
) -> EvaluationSummary:
    """Helper to load dataset, run evaluation, and return summary."""
    adapter = SyntheticBankingIntentAdapter()
    cases = adapter.load_and_adapt(dataset_path)
    runner = EvaluationRunner(predictor=predictor, criteria=criteria)
    return runner.run(cases, dataset_name=Path(dataset_path).name)
