"""
Reporting Module for Phase 0 Evaluation Foundation.

Produces:
1. Human-readable text report (formatted summary table, per-intent breakdown, failure details, verdict)
2. Machine-readable JSON report (structured schema for regression tracking and automation)
"""

import json
from pathlib import Path
import sys

from banking_eval.baseline import DeterministicBaseline
from banking_eval.runner import EvaluationSummary, run_evaluation
from banking_eval.schema import PredictionResult


def generate_human_readable_report(summary: EvaluationSummary) -> str:
    """Format an EvaluationSummary into a clear, human-readable terminal report."""
    lines = []
    lines.append("=" * 72)
    lines.append("       SECURE AGENTIC BANKING ASSISTANT - EVALUATION REPORT")
    lines.append("                  Phase 0: Evaluation Foundation")
    lines.append("=" * 72)
    lines.append(f"Timestamp:    {summary.timestamp}")
    lines.append(f"Dataset:      {summary.dataset_name}")
    lines.append(f"Total Cases:  {summary.total_cases}")
    lines.append(f"Passed Cases: {summary.passed_cases}")
    lines.append(f"Failed Cases: {summary.failed_cases}")
    lines.append("-" * 72)

    # Aggregate Task Quality Metrics
    m = summary.metrics
    lines.append("TASK QUALITY METRICS (Intent Classification)")
    lines.append(f"  Total Intent Cases Evaluated: {m.total_evaluated}")
    lines.append(f"  Quality Passed / Failed:      {m.quality_passed_count} / {m.quality_failed_count}")
    lines.append(f"  Overall Accuracy:             {m.accuracy:.2%} (target: >={summary.criteria.min_accuracy:.2%})")
    lines.append(f"  Macro-Precision:              {m.macro_precision:.4f}")
    lines.append(f"  Macro-Recall:                 {m.macro_recall:.4f}")
    lines.append(f"  Macro-F1 Score:               {m.macro_f1:.4f} (target: >={summary.criteria.min_macro_f1:.4f})")
    lines.append("")

    # Per-intent breakdown
    lines.append("PER-INTENT PERFORMANCE BREAKDOWN")
    lines.append(f"  {'Intent Label':<24} {'Support':<8} {'Precision':<10} {'Recall':<10} {'F1':<8}")
    lines.append("  " + "-" * 62)
    for intent_name, im in sorted(m.per_intent.items()):
        lines.append(
            f"  {intent_name:<24} {im.support:<8} {im.precision:<10.4f} {im.recall:<10.4f} {im.f1_score:<8.4f}"
        )
    lines.append("-" * 72)

    # Framework Safety-Veto Status
    lines.append("FRAMEWORK-LEVEL SAFETY-VETO STATUS")
    lines.append("  (Note: Mechanism validation only; not a banking authorization implementation)")
    lines.append(f"  Safety-Critical Test Cases:   {summary.safety_total_critical}")
    lines.append(f"  Safety Checks Passed:         {summary.safety_passed_critical}")
    lines.append(f"  Safety Checks Failed:         {summary.safety_failed_critical}")
    lines.append(f"  Safety Veto Enforced:         {summary.criteria.enforce_safety_veto}")
    lines.append(f"  Safety Veto Triggered:        {summary.safety_veto_triggered}")
    lines.append("-" * 72)

    # Individual Failures (if any)
    if summary.failures:
        lines.append("INDIVIDUAL FAILURE DETAILS")
        for idx, f in enumerate(summary.failures, 1):
            lines.append(f"  [{idx}] ID: {f['test_id']} (Category: {f['category']}, Safety-Critical: {f['is_safety_critical']})")
            lines.append(f"      Input:       \"{f['input']}\"")
            lines.append(f"      Expected:    Intent='{f['expected_intent']}', Policy='{f['expected_policy']}'")
            lines.append(f"      Predicted:   Intent='{f['predicted_intent']}', Policy='{f['predicted_policy']}'")
            lines.append(f"      Reason:      {f['failure_reason']}")
        lines.append("-" * 72)
    else:
        lines.append("INDIVIDUAL FAILURES: None (All test cases passed)")
        lines.append("-" * 72)

    # Overall Verdict
    lines.append(f"OVERALL EVALUATION RESULT: {'[ PASS ]' if summary.overall_passed else '[ FAIL ]'}")
    lines.append(f"Verdict: {summary.verdict}")
    lines.append("=" * 72)

    return "\n".join(lines)


def save_machine_readable_report(
    summary: EvaluationSummary, output_path: Path | str = "reports/evaluation_report.json"
) -> Path:
    """Save the evaluation summary as a structured JSON document."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        f.write(summary.model_dump_json(indent=2))

    return path


def main() -> int:
    """CLI entrypoint for running evaluation and printing/saving reports."""
    import argparse

    parser = argparse.ArgumentParser(description="Run Phase 0 Banking Assistant Evaluation")
    parser.add_argument(
        "--dataset",
        type=str,
        default="datasets/synthetic_banking_intents.json",
        help="Path to dataset file",
    )
    parser.add_argument(
        "--demo-mode",
        choices=["normal", "intentional-failure", "safety-veto"],
        default="normal",
        help="Demonstration mode: 'normal' (standard baseline), 'intentional-failure' (predicts wrong intent), 'safety-veto' (unsafe policy triggering veto)",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Error: Dataset not found at {dataset_path.resolve()}", file=sys.stderr)
        return 1

    # Configure predictor based on demo mode
    if args.demo_mode == "intentional-failure":
        class IntentionalFailurePredictor:
            def __init__(self):
                self._base = DeterministicBaseline(simulate_safe_behavior=True)

            def predict(self, text: str) -> PredictionResult:
                # Deliberately fail dispute cases to demonstrate failure reporting
                if "dispute" in text.lower() or "charging me twice" in text.lower():
                    return PredictionResult(
                        predicted_intent="incorrect_intent_prediction",
                        confidence=0.1,
                    )
                return self._base.predict(text)

        predictor = IntentionalFailurePredictor()
    elif args.demo_mode == "safety-veto":
        # Safe intent classification (100% accuracy), but simulated unsafe policy
        predictor = DeterministicBaseline(simulate_safe_behavior=False)
    else:
        predictor = DeterministicBaseline(simulate_safe_behavior=True)

    summary = run_evaluation(dataset_path=dataset_path, predictor=predictor)

    # Print human-readable report to console
    report_text = generate_human_readable_report(summary)
    print(report_text)

    # Save machine-readable JSON report
    output_json = Path("reports/evaluation_report.json")
    save_machine_readable_report(summary, output_json)
    print(f"\nMachine-readable report saved to: {output_json.resolve()}")

    return 0 if summary.overall_passed else 1


if __name__ == "__main__":
    sys.exit(main())
