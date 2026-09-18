"""
Synthetic Banking Simulator Package.

A deterministic, in-memory simulated banking environment for evaluation and testing.
Contains zero LLMs, zero ML models, and zero real financial infrastructure.
"""

from banking_simulator.clock import SimulatedClock
from banking_simulator.contracts import ErrorCode, FailureMode, OperationResult
from banking_simulator.models import (
    Account,
    AccountStatus,
    AccountType,
    Beneficiary,
    BeneficiaryStatus,
    Card,
    CardStatus,
    Transaction,
    TransactionStatus,
    TransactionType,
    User,
    UserStatus,
)
from banking_simulator.simulator import BankingSimulator

__all__ = [
    "Account",
    "AccountStatus",
    "AccountType",
    "BankingSimulator",
    "Beneficiary",
    "BeneficiaryStatus",
    "Card",
    "CardStatus",
    "ErrorCode",
    "FailureMode",
    "OperationResult",
    "SimulatedClock",
    "Transaction",
    "TransactionStatus",
    "TransactionType",
    "User",
    "UserStatus",
]
