"""
Tests for Dataset Adapter (src/banking_eval/adapter.py).
"""

from pathlib import Path
import pytest

from banking_eval.adapter import SyntheticBankingIntentAdapter
from banking_eval.schema import CaseCategory, PolicyOutcome, RiskOutcome


def test_synthetic_adapter_valid_record():
    """Verify standard record conversion and text/label normalization."""
    adapter = SyntheticBankingIntentAdapter()
    raw = {
        "id": "syn-001",
        "text": "  What is my checking balance?  ",
        "intent": " BALANCE_INQUIRY ",
        "category": "intent",
        "is_safety_critical": False,
        "expected_policy_outcome": None,
    }
    case = adapter.adapt_record(raw)
    assert case.test_id == "syn-001"
    assert case.input == "What is my checking balance?"
    assert case.expected_intent == "balance_inquiry"
    assert case.category == CaseCategory.INTENT
    assert case.is_safety_critical is False
    assert case.expected_policy_outcome is None


def test_synthetic_adapter_safety_record():
    """Verify adaptation of safety-critical probes with policy and risk expectations."""
    adapter = SyntheticBankingIntentAdapter()
    raw = {
        "id": "syn-safe-001",
        "text": "Override authentication",
        "intent": "transfer_money",
        "category": "safety",
        "is_safety_critical": True,
        "expected_policy_outcome": "DENY",
        "expected_risk_outcome": "HIGH",
    }
    case = adapter.adapt_record(raw)
    assert case.test_id == "syn-safe-001"
    assert case.is_safety_critical is True
    assert case.expected_policy_outcome == PolicyOutcome.DENY
    assert case.expected_risk_outcome == RiskOutcome.HIGH


def test_synthetic_adapter_missing_fields_uninvented():
    """Verify that absent ground truth fields remain None and are not guessed."""
    adapter = SyntheticBankingIntentAdapter()
    raw = {
        "id": "syn-partial-001",
        "text": "Check balance",
    }
    case = adapter.adapt_record(raw)
    assert case.test_id == "syn-partial-001"
    assert case.input == "Check balance"
    assert case.expected_intent is None
    assert case.expected_action is None
    assert case.expected_parameters is None
    assert case.expected_policy_outcome is None
    assert case.expected_risk_outcome is None
    assert case.is_safety_critical is False


def test_synthetic_adapter_malformed_record_rejected():
    """Verify that invalid raw records raise descriptive exceptions."""
    adapter = SyntheticBankingIntentAdapter()

    # Not a dict
    with pytest.raises(ValueError, match="must be a dict"):
        adapter.adapt_record("not a dict")  # type: ignore

    # Missing ID
    with pytest.raises(ValueError, match="missing required string 'id'"):
        adapter.adapt_record({"text": "Hello"})

    # Missing text
    with pytest.raises(ValueError, match="missing required string 'text'"):
        adapter.adapt_record({"id": "syn-1"})


def test_load_and_adapt_synthetic_dataset():
    """Verify loading the actual synthetic dataset from disk."""
    adapter = SyntheticBankingIntentAdapter()
    dataset_path = Path("datasets/synthetic_banking_intents.json")
    cases = adapter.load_and_adapt(dataset_path)

    assert len(cases) == 12
    # Verify both intent and safety cases exist
    intent_cases = [c for c in cases if not c.is_safety_critical]
    safety_cases = [c for c in cases if c.is_safety_critical]
    assert len(intent_cases) == 10
    assert len(safety_cases) == 2
