"""
Strongly typed, immutable transaction request contract for Transaction Safety.
"""

from decimal import Decimal
import hashlib
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from banking_security.actions import BankingAction


class TransactionRequest(BaseModel):
    """
    Immutable representation of the exact structured transaction parameters.
    The safety layer evaluates these exact parameters without silent alteration or repair.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_type: BankingAction = Field(
        ...,
        description="BankingAction: TRANSFER (direct) or TRANSFER_TO_BENEFICIARY",
    )
    source_account_id: str = Field(..., min_length=1, description="Originating account ID")
    destination_account_id: Optional[str] = Field(
        default=None,
        description="Destination account ID (required for TRANSFER, forbidden for TRANSFER_TO_BENEFICIARY)",
    )
    beneficiary_id: Optional[str] = Field(
        default=None,
        description="Beneficiary ID (required for TRANSFER_TO_BENEFICIARY, forbidden for TRANSFER)",
    )
    amount: Decimal = Field(..., gt=Decimal("0.00"), description="Transfer amount in exact Decimal")
    currency: str = Field(default="INR", min_length=3, max_length=3, description="ISO-4217 uppercase currency code")
    idempotency_key: str = Field(..., min_length=1, description="Mandatory non-empty idempotency key")

    @field_validator("amount", mode="before")
    @classmethod
    def reject_float_amount(cls, v: Any) -> Any:
        if isinstance(v, float):
            raise ValueError("Floating-point amounts are strictly prohibited; use Decimal or exact decimal string.")
        return v

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Idempotency key must be a non-empty, non-whitespace string.")
        return v.strip()

    @model_validator(mode="after")
    def validate_strict_contract(self) -> "TransactionRequest":
        # 1. Reject non-finite amounts
        if not self.amount.is_finite():
            raise ValueError("Amount must be a finite monetary value.")

        # 2. Strict precision check: reject amounts with more than 2 decimal digits.
        # No silent rounding or repair is permitted.
        # (amount * 100) % 1 must equal 0.
        if (self.amount * 100) % 1 != Decimal("0"):
            raise ValueError(
                f"Amount {self.amount} has precision beyond 2 decimal places. Silent rounding is prohibited."
            )

        # 3. Currency must be uppercase ISO code
        if self.currency != self.currency.strip().upper():
            raise ValueError(f"Currency '{self.currency}' must be uppercase 3-letter ISO code.")

        # 4. Enforce strict operation-to-target contract
        if self.operation_type == BankingAction.TRANSFER:
            if not self.destination_account_id or not self.destination_account_id.strip():
                raise ValueError("TRANSFER requires a non-empty destination_account_id.")
            if self.beneficiary_id is not None:
                raise ValueError("TRANSFER does not accept beneficiary_id; use destination_account_id.")
        elif self.operation_type == BankingAction.TRANSFER_TO_BENEFICIARY:
            if not self.beneficiary_id or not self.beneficiary_id.strip():
                raise ValueError("TRANSFER_TO_BENEFICIARY requires a non-empty beneficiary_id.")
            if self.destination_account_id is not None:
                raise ValueError("TRANSFER_TO_BENEFICIARY does not accept destination_account_id directly.")
        else:
            raise ValueError(f"Unsupported transaction operation_type: {self.operation_type}")

        return self

    @property
    def target_reference(self) -> str:
        """The target account or beneficiary identifier."""
        return self.destination_account_id or self.beneficiary_id or ""

    @property
    def canonical_amount_str(self) -> str:
        """
        Lossless canonical 2-decimal monetary representation.
        Normalizes equivalent representations without modifying precision (e.g. 100.1 and 100.10 -> '100.10').
        """
        return f"{self.amount.quantize(Decimal('0.01')):.2f}"

    def compute_fingerprint(self) -> str:
        """
        Deterministically construct a SHA-256 hex digest covering the exact physical transaction parameters:
        (operation_type, source_account_id, target_reference, canonical_amount_str, currency).
        """
        payload = (
            f"{self.operation_type}:"
            f"{self.source_account_id}:"
            f"{self.target_reference}:"
            f"{self.canonical_amount_str}:"
            f"{self.currency}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
