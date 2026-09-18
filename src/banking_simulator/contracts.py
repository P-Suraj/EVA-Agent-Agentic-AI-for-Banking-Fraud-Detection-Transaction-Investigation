"""
Operation Result Contracts and Error Codes for Synthetic Banking Simulator.
"""

from enum import StrEnum
from typing import Generic, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ErrorCode(StrEnum):
    SUCCESS = "SUCCESS"
    INVALID_AMOUNT = "INVALID_AMOUNT"
    ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
    ACCOUNT_FROZEN = "ACCOUNT_FROZEN"
    ACCOUNT_INACTIVE = "ACCOUNT_INACTIVE"
    BENEFICIARY_NOT_FOUND = "BENEFICIARY_NOT_FOUND"
    BENEFICIARY_OWNERSHIP_MISMATCH = "BENEFICIARY_OWNERSHIP_MISMATCH"
    BENEFICIARY_NOT_VERIFIED = "BENEFICIARY_NOT_VERIFIED"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    CARD_NOT_FOUND = "CARD_NOT_FOUND"
    CARD_ALREADY_FROZEN = "CARD_ALREADY_FROZEN"
    SIMULATED_FAILURE = "SIMULATED_FAILURE"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    PERMISSION_DENIED = "PERMISSION_DENIED"


class FailureMode(StrEnum):
    NONE = "NONE"
    PRE_COMMIT_FAILURE = "PRE_COMMIT_FAILURE"


class OperationResult(BaseModel, Generic[T]):
    """
    Standardized, typed operation result contract.
    Guarantees deterministic error codes without leaking unhandled exceptions.
    """
    model_config = ConfigDict(extra="forbid")

    success: bool = Field(..., description="True if operation completed successfully")
    error_code: ErrorCode = Field(..., description="Deterministic machine-readable status/error code")
    message: str = Field(..., description="Human-readable description of outcome")
    data: Optional[T] = Field(default=None, description="Resulting entity or payload on success")
    transaction_id: Optional[str] = Field(default=None, description="ID of generated transaction if committed")
