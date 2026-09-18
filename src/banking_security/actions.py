"""
Actions and Resource Targets for Banking Security.
"""

from enum import StrEnum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class BankingAction(StrEnum):
    READ_ACCOUNT = "READ_ACCOUNT"
    READ_BALANCE = "READ_BALANCE"
    READ_TRANSACTIONS = "READ_TRANSACTIONS"
    READ_BENEFICIARY = "READ_BENEFICIARY"
    READ_CARD = "READ_CARD"
    TRANSFER = "TRANSFER"
    TRANSFER_TO_BENEFICIARY = "TRANSFER_TO_BENEFICIARY"
    FREEZE_CARD = "FREEZE_CARD"


class ResourceType(StrEnum):
    ACCOUNT = "ACCOUNT"
    BENEFICIARY = "BENEFICIARY"
    CARD = "CARD"
    TRANSACTION = "TRANSACTION"


class ResourceTarget(BaseModel):
    """
    Immutable representation of the target resource(s) for policy evaluation.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    resource_type: ResourceType = Field(..., description="Type of primary resource")
    resource_id: str = Field(..., min_length=1, description="Identifier of primary resource")
    secondary_resource_id: Optional[str] = Field(
        default=None,
        description="Secondary resource identifier if applicable (e.g. beneficiary ID or destination account)",
    )
