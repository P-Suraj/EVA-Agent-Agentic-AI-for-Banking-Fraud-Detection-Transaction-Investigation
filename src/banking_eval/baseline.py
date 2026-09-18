"""
Deterministic Baseline Classifier for Phase 0 Evaluation.

A transparent, rule-based classifier used to validate the evaluation pipeline.
Contains zero LLMs, zero ML models, and zero external dependencies.
"""

from typing import Optional
from banking_eval.schema import PolicyOutcome, PredictionResult, RiskOutcome


class DeterministicBaseline:
    """
    Rule-based keyword matching baseline.

    Purpose: Validate evaluation runner, metrics calculation, failure reporting,
    and safety-veto mechanisms without introducing non-deterministic ML/LLM systems.
    """

    def __init__(self, simulate_safe_behavior: bool = True):
        """
        Initialize the deterministic baseline.

        :param simulate_safe_behavior: When True, simulated security probe triggers
               produce DENY outcomes (safe baseline). When False, produces ALLOW or None,
               used to demonstrate framework-level safety-veto triggers.
        """
        self.simulate_safe_behavior = simulate_safe_behavior

    def predict(self, text: str) -> PredictionResult:
        """
        Deterministically predict intent and simulated policy outcome based on keyword rules.
        """
        text_lower = text.lower()

        # 1. Check for simulated safety probe keywords
        is_safety_probe = any(
            kw in text_lower for kw in ["override security", "bypass authentication", "without 2fa"]
        )

        policy_outcome: Optional[PolicyOutcome] = None
        risk_outcome: Optional[RiskOutcome] = None

        if is_safety_probe:
            if self.simulate_safe_behavior:
                policy_outcome = PolicyOutcome.DENY
                risk_outcome = RiskOutcome.HIGH
            else:
                # Deliberately unsafe behavior for safety-veto testing
                policy_outcome = PolicyOutcome.ALLOW
                risk_outcome = RiskOutcome.LOW

        # 2. Deterministic intent matching rules (ordered by specificity)
        intent = self._match_intent(text_lower)

        return PredictionResult(
            predicted_intent=intent,
            predicted_policy_outcome=policy_outcome,
            predicted_risk_outcome=risk_outcome,
            confidence=1.0 if intent != "unknown_intent" else 0.0,
        )

    def _match_intent(self, text_lower: str) -> str:
        """Ordered keyword rules to classify intent."""
        if any(kw in text_lower for kw in ["dispute", "charging me twice"]):
            return "dispute_charge"
        if any(kw in text_lower for kw in ["freeze", "debit card", "credit card", "replacement", "card number", "card"]):
            return "card_issue"
        if any(kw in text_lower for kw in ["transfer", "wire", "send $"]):
            return "transfer_money"
        if any(kw in text_lower for kw in ["charge from", "transactions", "transaction"]):
            return "transaction_inquiry"
        if any(kw in text_lower for kw in ["balance", "how much money"]):
            return "balance_inquiry"

        return "unknown_intent"
