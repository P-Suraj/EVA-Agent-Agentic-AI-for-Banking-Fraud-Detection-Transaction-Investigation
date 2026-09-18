"""
Contracts for Deterministic Policy Decisions and Results.
"""

from enum import StrEnum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from banking_security.actions import BankingAction


class PolicyDecision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class PolicyReasonCode(StrEnum):
    AUTHORIZED = "AUTHORIZED"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    UNKNOWN_PRINCIPAL = "UNKNOWN_PRINCIPAL"
    USER_SUSPENDED = "USER_SUSPENDED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    OWNERSHIP_MISMATCH = "OWNERSHIP_MISMATCH"
    BENEFICIARY_OWNERSHIP_MISMATCH = "BENEFICIARY_OWNERSHIP_MISMATCH"
    BENEFICIARY_NOT_VERIFIED = "BENEFICIARY_NOT_VERIFIED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    FAIL_CLOSED_ERROR = "FAIL_CLOSED_ERROR"


class PolicyResult(BaseModel):
    """
    Standardized, machine-readable authorization evaluation result.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: PolicyDecision = Field(..., description="ALLOW or DENY")
    reason_code: PolicyReasonCode = Field(..., description="Machine-readable outcome code")
    message: str = Field(..., description="Explanatory text for audit/debugging")
    evaluated_at: str = Field(..., description="Deterministic ISO-8601 timestamp")
    principal_id: Optional[str] = Field(default=None, description="Principal evaluated if authenticated")
    action: BankingAction = Field(..., description="Action evaluated")
    resource_id: Optional[str] = Field(default=None, description="Primary resource ID evaluated")
