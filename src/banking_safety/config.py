"""
Configuration for Transaction Safety policies and limits.
"""

from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class TransactionSafetyConfig(BaseModel):
    """
    Immutable, configurable transaction safety policy parameters.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    per_transaction_limit: Decimal = Field(
        default=Decimal("25000.00"),
        gt=Decimal("0.00"),
        description="Maximum allowed amount for a single outbound transfer",
    )
    daily_transfer_limit: Decimal = Field(
        default=Decimal("50000.00"),
        gt=Decimal("0.00"),
        description="Maximum cumulative transfer amount from an account within a UTC calendar day",
    )
    velocity_window_seconds: int = Field(
        default=3600,
        gt=0,
        description="Rolling time window in seconds for velocity evaluation (default 1 hour)",
    )
    velocity_count_limit: int = Field(
        default=3,
        gt=0,
        description="Maximum count of outbound transfers permitted within the velocity window",
    )
    step_up_threshold: Decimal = Field(
        default=Decimal("10000.00"),
        gt=Decimal("0.00"),
        description="Threshold amount at or above which step-up approval is required",
    )
    step_up_valid_duration_seconds: int = Field(
        default=300,
        gt=0,
        description="Validity duration in seconds for simulated step-up approval tokens (default 5 mins)",
    )
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        description="Enforced operating currency; cross-currency conversion is prohibited",
    )
