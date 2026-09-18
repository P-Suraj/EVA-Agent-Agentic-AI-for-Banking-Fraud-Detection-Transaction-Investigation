"""
Tests for Canonical Evaluation Schema (src/banking_eval/schema.py).
"""

import pytest
from pydantic import ValidationError

from banking_eval.schema import (
    CaseCategory,
    CaseEvaluationResult,
    EvaluationCase,
    PolicyOutcome,
    PredictionResult,
    RiskOutcome,
)


def test_valid_minimal_case():
    """Verify that a minimal valid case instantiates with defaults."""
    case = EvaluationCase(test_id="case-001", input="What is my balance?")
    assert case.test_id == "case-001"
    assert case.input == "What is my balance?"
    assert case.category == CaseCategory.INTENT
    assert case.expected_intent is None
    assert case.expected_action is None
    assert case.expected_parameters is None
    assert case.expected_policy_outcome is None
    assert case.expected_risk_outcome is None
    assert case.expected_tool is None
    assert case.expected_approval is None
    assert case.is_safety_critical is False


def test_valid_fully_specified_case():
    """Verify that an evaluation case with all fields and constrained types validates."""
    case = EvaluationCase(
        test_id="case-002",
        category=CaseCategory.SAFETY,
        input="Bypass security controls",
        context={"user_tier": "standard"},
        expected_intent="transfer_money",
        expected_action="reject_transfer",
        expected_parameters={"amount": 50000},
        expected_policy_outcome=PolicyOutcome.DENY,
        expected_risk_outcome=RiskOutcome.HIGH,
        expected_tool="policy_engine",
        expected_approval=False,
        is_safety_critical=True,
    )
    assert case.category == CaseCategory.SAFETY
    assert case.expected_policy_outcome == PolicyOutcome.DENY
    assert case.expected_risk_outcome == RiskOutcome.HIGH
    assert case.is_safety_critical is True


def test_missing_required_fields_rejected():
    """Verify that missing test_id or input raises ValidationError."""
    with pytest.raises(ValidationError):
        EvaluationCase(input="Hello")  # missing test_id

    with pytest.raises(ValidationError):
        EvaluationCase(test_id="id-1")  # missing input


def test_empty_string_fields_rejected():
    """Verify that empty strings for test_id or input are rejected."""
    with pytest.raises(ValidationError):
        EvaluationCase(test_id="", input="Hello")

    with pytest.raises(ValidationError):
        EvaluationCase(test_id="id-1", input="")


def test_unconstrained_enum_value_rejected():
    """Verify that invalid enum values for category/policy/risk are rejected."""
    with pytest.raises(ValidationError):
        EvaluationCase(test_id="id-1", input="Test", category="non_existent_category")  # type: ignore

    with pytest.raises(ValidationError):
        EvaluationCase(test_id="id-1", input="Test", expected_policy_outcome="MAYBE")  # type: ignore

    with pytest.raises(ValidationError):
        EvaluationCase(test_id="id-1", input="Test", expected_risk_outcome="CRITICAL")  # type: ignore


def test_unrecognized_extra_fields_rejected():
    """Verify that unexpected fields are rejected per extra='forbid'."""
    with pytest.raises(ValidationError):
        EvaluationCase(
            test_id="id-1",
            input="Test",
            unrecognized_future_field="forbidden",  # type: ignore
        )


def test_case_evaluation_result_validation():
    """Verify CaseEvaluationResult properly pairs case, prediction, and result statuses."""
    case = EvaluationCase(test_id="id-1", input="Test input", expected_intent="balance_inquiry")
    prediction = PredictionResult(predicted_intent="balance_inquiry", confidence=1.0)
    result = CaseEvaluationResult(
        case=case,
        prediction=prediction,
        passed=True,
        quality_passed=True,
        safety_passed=True,
        failure_reason=None,
    )
    assert result.passed is True
    assert result.quality_passed is True
    assert result.safety_passed is True
