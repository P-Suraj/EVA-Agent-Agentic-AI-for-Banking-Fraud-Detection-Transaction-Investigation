"""
Contracts and Result Models for Transaction Safety and Deterministic Execution Gate.
"""

from enum import StrEnum
from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

from banking_security.contracts import PolicyResult

T = TypeVar("T")


class SafetyDecision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    STEP_UP_REQUIRED = "STEP_UP_REQUIRED"


class SafetyReasonCode(StrEnum):
    SAFETY_ALLOWED = "SAFETY_ALLOWED"
    PER_TRANSACTION_LIMIT_EXCEEDED = "PER_TRANSACTION_LIMIT_EXCEEDED"
    DAILY_LIMIT_EXCEEDED = "DAILY_LIMIT_EXCEEDED"
    VELOCITY_LIMIT_EXCEEDED = "VELOCITY_LIMIT_EXCEEDED"
    IDEMPOTENCY_REPLAY = "IDEMPOTENCY_REPLAY"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    MISSING_IDEMPOTENCY_KEY = "MISSING_IDEMPOTENCY_KEY"
    STEP_UP_REQUIRED = "STEP_UP_REQUIRED"
    APPROVAL_MISSING = "APPROVAL_MISSING"
    APPROVAL_MISMATCH = "APPROVAL_MISMATCH"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    APPROVAL_ALREADY_USED = "APPROVAL_ALREADY_USED"
    UNTRUSTED_APPROVAL = "UNTRUSTED_APPROVAL"
    INVALID_TRANSACTION_REQUEST = "INVALID_TRANSACTION_REQUEST"
    CURRENCY_UNSUPPORTED = "CURRENCY_UNSUPPORTED"
    FAIL_CLOSED_ERROR = "FAIL_CLOSED_ERROR"


class GateStage(StrEnum):
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    TRANSACTION_SAFETY = "TRANSACTION_SAFETY"
    SIMULATOR_EXECUTION = "SIMULATOR_EXECUTION"


class SafetyResult(BaseModel):
    """
    Machine-readable safety evaluation result emitted by TransactionSafetyEngine.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: SafetyDecision = Field(..., description="Safety decision: ALLOW, DENY, or STEP_UP_REQUIRED")
    reason_code: SafetyReasonCode = Field(..., description="Deterministic machine-readable reason code")
    message: str = Field(..., description="Human-readable audit explanation")
    fingerprint: Optional[str] = Field(default=None, description="Deterministic transaction fingerprint evaluated")
    evaluated_at: str = Field(..., description="ISO-8601 timestamp of evaluation from SimulatedClock")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Diagnostic/limit calculation metadata")


class ExecutionGateResult(BaseModel, Generic[T]):
    """
    Standardized result contract for all operations dispatched through SecureExecutionGateway.
    Provides complete auditability while maintaining full compatibility with OperationResult semantics.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    success: bool = Field(..., description="True if operation completed successfully")
    error_code: str = Field(..., description="Deterministic error or status code")
    message: str = Field(..., description="Human-readable outcome description")
    data: Optional[T] = Field(default=None, description="Resulting entity or payload on success")
    transaction_id: Optional[str] = Field(default=None, description="Committed transaction identifier if generated")
    policy_result: Optional[PolicyResult] = Field(default=None, description="Layer 2 authorization outcome if evaluated")
    safety_result: Optional[SafetyResult] = Field(default=None, description="Layer 3 safety outcome if evaluated")
    cached_replay: bool = Field(default=False, description="True if result was served from authoritative idempotency cache")
    gate_stage: Optional[GateStage] = Field(default=None, description="Execution gate stage at outcome resolution")
