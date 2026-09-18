"""
Domain Models for Synthetic Banking Simulator.

All monetary values are represented as exact Decimal quantities.
Floating-point arithmetic is strictly prohibited.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class AccountType(StrEnum):
    CHECKING = "CHECKING"
    SAVINGS = "SAVINGS"


class AccountStatus(StrEnum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


class BeneficiaryStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PENDING = "PENDING"


class CardStatus(StrEnum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"


class TransactionType(StrEnum):
    TRANSFER = "TRANSFER"


class TransactionStatus(StrEnum):
    POSTED = "POSTED"
    FAILED = "FAILED"  # Reserved for future phases; Phase 1 persists only POSTED records.


class User(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    user_id: str = Field(..., min_length=1, description="Unique user identifier")
    name: str = Field(..., min_length=1, description="Customer full name")
    status: UserStatus = Field(default=UserStatus.ACTIVE, description="User account standing")


class Account(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    account_id: str = Field(..., min_length=1, description="Unique account identifier")
    user_id: str = Field(..., min_length=1, description="Owner user identifier")
    account_type: AccountType = Field(..., description="Account category (CHECKING, SAVINGS)")
    currency: str = Field(default="INR", min_length=3, max_length=3, description="ISO-4217 currency code")
    balance: Decimal = Field(..., ge=Decimal("0.00"), description="Available balance (exact Decimal)")
    status: AccountStatus = Field(default=AccountStatus.ACTIVE, description="Account operational status")


class Beneficiary(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    beneficiary_id: str = Field(..., min_length=1, description="Unique beneficiary identifier")
    owner_user_id: str = Field(..., min_length=1, description="User who registered this beneficiary")
    name: str = Field(..., min_length=1, description="Beneficiary display name")
    account_reference: str = Field(..., min_length=1, description="Target account identifier in simulator")
    status: BeneficiaryStatus = Field(default=BeneficiaryStatus.VERIFIED, description="Verification status")


class Transaction(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    transaction_id: str = Field(..., min_length=1, description="Deterministic transaction identifier")
    transaction_type: TransactionType = Field(default=TransactionType.TRANSFER, description="Transaction type")
    source_account_id: str = Field(..., min_length=1, description="Originating account ID")
    destination_account_id: str = Field(..., min_length=1, description="Destination account ID")
    beneficiary_id: Optional[str] = Field(default=None, description="Associated beneficiary ID if applicable")
    amount: Decimal = Field(..., gt=Decimal("0.00"), description="Transfer amount (exact Decimal)")
    currency: str = Field(..., min_length=3, max_length=3, description="Currency code")
    status: TransactionStatus = Field(default=TransactionStatus.POSTED, description="Transaction status")
    timestamp: str = Field(..., description="Deterministic ISO-8601 timestamp from SimulatedClock")
    reference: Optional[str] = Field(default=None, description="External or idempotency reference")


class Card(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    card_id: str = Field(..., min_length=1, description="Unique card identifier")
    user_id: str = Field(..., min_length=1, description="Cardholder user identifier")
    account_id: str = Field(..., min_length=1, description="Linked account identifier")
    card_number_masked: str = Field(..., min_length=1, description="Masked card number for display")
    status: CardStatus = Field(default=CardStatus.ACTIVE, description="Card operational status")
