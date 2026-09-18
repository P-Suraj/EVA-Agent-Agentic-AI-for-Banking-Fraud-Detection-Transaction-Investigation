"""
Canonical Evaluation Schemas for Phase 0 Evaluation Foundation.

NOTE: This schema defines evaluation data structures for the evaluation framework.
It does NOT implement or enforce banking authorization, authentication, or transactions.
"""

from enum import StrEnum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class CaseCategory(StrEnum):
    """Constrained categories for evaluation cases."""
    INTENT = "intent"
    SAFETY = "safety"
    TRANSACTION = "transaction"
    GENERAL = "general"


class PolicyOutcome(StrEnum):
    """Constrained policy outcomes for simulated evaluation expectations."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    ESCALATE = "ESCALATE"


class RiskOutcome(StrEnum):
    """Constrained risk levels for simulated evaluation expectations."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EvaluationCase(BaseModel):
    """
    Typed canonical evaluation-case schema.

    Supports various dataset formats without forcing all fields to be populated.
    Missing ground truth fields remain None (unavailable) rather than guessed.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    test_id: str = Field(..., min_length=1, description="Unique identifier for the test case")
    category: CaseCategory = Field(default=CaseCategory.INTENT, description="Evaluation category")
    input: str = Field(..., min_length=1, description="Customer text utterance or query")
    context: Optional[dict[str, Any]] = Field(default=None, description="Optional conversation context")

    # Ground truth expectations (optional to support partial datasets like BANKING77)
    expected_intent: Optional[str] = Field(default=None, description="Expected banking intent label")
    expected_action: Optional[str] = Field(default=None, description="Expected action")
    expected_parameters: Optional[dict[str, Any]] = Field(default=None, description="Expected parameters")
    expected_policy_outcome: Optional[PolicyOutcome] = Field(default=None, description="Expected policy outcome")
    expected_risk_outcome: Optional[RiskOutcome] = Field(default=None, description="Expected risk outcome")
    expected_tool: Optional[str] = Field(default=None, description="Expected tool invocation")
    expected_approval: Optional[bool] = Field(default=None, description="Expected human/system approval flag")

    # Evaluation framework veto mechanism flag
    is_safety_critical: bool = Field(
        default=False,
        description="Flag indicating this case is evaluated under the framework safety-veto rule"
    )


class PredictionResult(BaseModel):
    """
    Prediction or output produced by a baseline classifier or predictor.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    predicted_intent: Optional[str] = Field(default=None, description="Predicted intent label")
    predicted_action: Optional[str] = Field(default=None, description="Predicted action")
    predicted_parameters: Optional[dict[str, Any]] = Field(default=None, description="Predicted parameters")
    predicted_policy_outcome: Optional[PolicyOutcome] = Field(default=None, description="Predicted policy outcome")
    predicted_risk_outcome: Optional[RiskOutcome] = Field(default=None, description="Predicted risk outcome")
    predicted_tool: Optional[str] = Field(default=None, description="Predicted tool")
    predicted_approval: Optional[bool] = Field(default=None, description="Predicted approval")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Prediction confidence")


class CaseEvaluationResult(BaseModel):
    """
    Evaluation result for an individual test case, separating quality and safety outcomes.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    case: EvaluationCase
    prediction: PredictionResult
    passed: bool = Field(..., description="Overall pass status for this specific case")
    quality_passed: bool = Field(..., description="Pass status for task quality (e.g. intent matching)")
    safety_passed: bool = Field(..., description="Pass status for safety expectations")
    failure_reason: Optional[str] = Field(default=None, description="Explanation of failure if applicable")
