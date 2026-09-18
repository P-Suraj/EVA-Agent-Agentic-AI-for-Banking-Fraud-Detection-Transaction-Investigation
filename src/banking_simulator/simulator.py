"""
Synthetic Banking Simulator Core.

In-memory, deterministic simulated banking environment providing controlled
state, exact Decimal accounting, failure injection, and idempotency tracking.
Zero LLMs, zero ML models, and zero external infrastructure.
"""

from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from banking_simulator.clock import SimulatedClock
from banking_simulator.contracts import ErrorCode, FailureMode, OperationResult
from banking_simulator.fixtures import (
    get_default_accounts,
    get_default_beneficiaries,
    get_default_cards,
    get_default_users,
)
from banking_simulator.models import (
    Account,
    AccountStatus,
    Beneficiary,
    BeneficiaryStatus,
    Card,
    CardStatus,
    Transaction,
    TransactionStatus,
    TransactionType,
    User,
)


class BankingSimulator:
    """
    Isolated, deterministic in-memory banking state machine.
    """

    def __init__(
        self,
        clock: Optional[SimulatedClock] = None,
        seed_default_fixtures: bool = True,
    ):
        self._clock = clock or SimulatedClock()
        self._tx_counter = 0
        self._failure_mode = FailureMode.NONE

        # Independent in-memory stores
        if seed_default_fixtures:
            self._users: dict[str, User] = get_default_users()
            self._accounts: dict[str, Account] = get_default_accounts()
            self._beneficiaries: dict[str, Beneficiary] = get_default_beneficiaries()
            self._cards: dict[str, Card] = get_default_cards()
        else:
            self._users = {}
            self._accounts = {}
            self._beneficiaries = {}
            self._cards = {}

        self._transactions: dict[str, Transaction] = {}
        # Stores: idempotency_key -> (fingerprint_dict, cached_OperationResult)
        self._idempotency_store: dict[str, tuple[dict[str, str], OperationResult[Transaction]]] = {}

    # --------------------------------------------------------------------------
    # Deterministic ID Generation
    # --------------------------------------------------------------------------

    def _generate_tx_id(self) -> str:
        self._tx_counter += 1
        return f"tx_{self._tx_counter:04d}"

    # --------------------------------------------------------------------------
    # Failure Injection Control
    # --------------------------------------------------------------------------

    def inject_failure(self, mode: FailureMode) -> None:
        """Configure failure mode for testing error handling and state consistency."""
        self._failure_mode = mode

    # --------------------------------------------------------------------------
    # Amount Normalization & Validation Helper
    # --------------------------------------------------------------------------

    @staticmethod
    def _normalize_amount(amount: Any) -> Optional[Decimal]:
        """
        Deterministically parse and normalize monetary amounts to 2 decimal places.
        Floating-point numbers are strictly disallowed to prevent precision corruption.
        Returns None if amount is invalid or <= 0.
        """
        if isinstance(amount, float):
            return None

        try:
            dec = Decimal(str(amount))
            # Validate positive value
            if dec <= Decimal("0.00"):
                return None
            # Quantize to 2 decimal places
            return dec.quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            return None

    # --------------------------------------------------------------------------
    # Read Operations
    # --------------------------------------------------------------------------

    def get_user(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    def get_account(self, account_id: str) -> Optional[Account]:
        return self._accounts.get(account_id)

    def get_balance(self, account_id: str) -> Optional[Decimal]:
        acc = self.get_account(account_id)
        return acc.balance if acc else None

    def get_transactions(self, account_id: str) -> list[Transaction]:
        return [
            tx
            for tx in self._transactions.values()
            if tx.source_account_id == account_id or tx.destination_account_id == account_id
        ]

    def get_beneficiary(self, owner_user_id: str, beneficiary_id: str) -> Optional[Beneficiary]:
        ben = self._beneficiaries.get(beneficiary_id)
        if ben and ben.owner_user_id == owner_user_id:
            return ben
        return None

    def get_card(self, card_id: str) -> Optional[Card]:
        return self._cards.get(card_id)

    # --------------------------------------------------------------------------
    # Card Operations
    # --------------------------------------------------------------------------

    def freeze_card(self, card_id: str) -> OperationResult[Card]:
        card = self._cards.get(card_id)
        if not card:
            return OperationResult(
                success=False,
                error_code=ErrorCode.CARD_NOT_FOUND,
                message=f"Card '{card_id}' not found",
            )

        if card.status == CardStatus.FROZEN:
            return OperationResult(
                success=False,
                error_code=ErrorCode.CARD_ALREADY_FROZEN,
                message=f"Card '{card_id}' is already frozen",
                data=card,
            )

        card.status = CardStatus.FROZEN
        return OperationResult(
            success=True,
            error_code=ErrorCode.SUCCESS,
            message=f"Card '{card_id}' successfully frozen",
            data=card,
        )

    # --------------------------------------------------------------------------
    # Transfer Operations
    # --------------------------------------------------------------------------

    def transfer(
        self,
        source_account_id: str,
        destination_account_id: str,
        amount: Any,
        currency: str = "INR",
        idempotency_key: Optional[str] = None,
    ) -> OperationResult[Transaction]:
        """
        Execute an account-to-account transfer following strict deterministic validation precedence.
        """
        return self._execute_transfer(
            operation_name="transfer",
            source_account_id=source_account_id,
            destination_account_id=destination_account_id,
            target_reference=destination_account_id,
            beneficiary_id=None,
            amount=amount,
            currency=currency,
            idempotency_key=idempotency_key,
        )

    def transfer_to_beneficiary(
        self,
        owner_user_id: str,
        source_account_id: str,
        beneficiary_id: str,
        amount: Any,
        currency: str = "INR",
        idempotency_key: Optional[str] = None,
    ) -> OperationResult[Transaction]:
        """
        Execute a transfer to a registered verified beneficiary after verifying ownership.
        """
        # Beneficiary existence check
        ben = self._beneficiaries.get(beneficiary_id)
        if not ben:
            return OperationResult(
                success=False,
                error_code=ErrorCode.BENEFICIARY_NOT_FOUND,
                message=f"Beneficiary '{beneficiary_id}' not found",
            )

        # Beneficiary ownership check
        if ben.owner_user_id != owner_user_id:
            return OperationResult(
                success=False,
                error_code=ErrorCode.BENEFICIARY_OWNERSHIP_MISMATCH,
                message=f"Beneficiary '{beneficiary_id}' does not belong to user '{owner_user_id}'",
            )

        # Beneficiary verification check
        if ben.status != BeneficiaryStatus.VERIFIED:
            return OperationResult(
                success=False,
                error_code=ErrorCode.BENEFICIARY_NOT_VERIFIED,
                message=f"Beneficiary '{beneficiary_id}' is not verified (status: {ben.status})",
            )

        destination_account_id = ben.account_reference

        return self._execute_transfer(
            operation_name="transfer_to_beneficiary",
            source_account_id=source_account_id,
            destination_account_id=destination_account_id,
            target_reference=beneficiary_id,
            beneficiary_id=beneficiary_id,
            amount=amount,
            currency=currency,
            idempotency_key=idempotency_key,
        )

    # --------------------------------------------------------------------------
    # Internal Transfer Execution Engine
    # --------------------------------------------------------------------------

    def _execute_transfer(
        self,
        operation_name: str,
        source_account_id: str,
        destination_account_id: str,
        target_reference: str,
        beneficiary_id: Optional[str],
        amount: Any,
        currency: str,
        idempotency_key: Optional[str],
    ) -> OperationResult[Transaction]:
        """
        Internal implementation enforcing the strict 11-step validation ordering.
        """
        # Step 1: Idempotency Check (Check cached successful request)
        fingerprint = None
        norm_amount = self._normalize_amount(amount)
        norm_currency = currency.strip().upper() if isinstance(currency, str) else ""

        if idempotency_key is not None:
            norm_amount_str = str(norm_amount) if norm_amount is not None else str(amount)
            fingerprint = {
                "operation": operation_name,
                "source_account_id": source_account_id,
                "target_reference": target_reference,
                "amount": norm_amount_str,
                "currency": norm_currency,
            }
            if idempotency_key in self._idempotency_store:
                cached_fp, cached_result = self._idempotency_store[idempotency_key]
                if cached_fp == fingerprint:
                    return cached_result
                return OperationResult(
                    success=False,
                    error_code=ErrorCode.IDEMPOTENCY_CONFLICT,
                    message=f"Idempotency key '{idempotency_key}' already used with different parameters",
                )

        # Step 2: Amount Validation
        if norm_amount is None:
            return OperationResult(
                success=False,
                error_code=ErrorCode.INVALID_AMOUNT,
                message="Transfer amount must be a positive monetary value with at most 2 decimal places",
            )

        # Step 3: Source Account Existence
        source_acc = self._accounts.get(source_account_id)
        if not source_acc:
            return OperationResult(
                success=False,
                error_code=ErrorCode.ACCOUNT_NOT_FOUND,
                message=f"Source account '{source_account_id}' not found",
            )

        # Step 4: Destination Account Existence
        dest_acc = self._accounts.get(destination_account_id)
        if not dest_acc:
            return OperationResult(
                success=False,
                error_code=ErrorCode.ACCOUNT_NOT_FOUND,
                message=f"Destination account '{destination_account_id}' not found",
            )

        # Step 5: Source Account Status Check
        if source_acc.status == AccountStatus.FROZEN:
            return OperationResult(
                success=False,
                error_code=ErrorCode.ACCOUNT_FROZEN,
                message=f"Source account '{source_account_id}' is frozen",
            )
        if source_acc.status != AccountStatus.ACTIVE:
            return OperationResult(
                success=False,
                error_code=ErrorCode.ACCOUNT_INACTIVE,
                message=f"Source account '{source_account_id}' is inactive",
            )

        # Step 6: Destination Account Status Check
        if dest_acc.status == AccountStatus.FROZEN:
            return OperationResult(
                success=False,
                error_code=ErrorCode.ACCOUNT_FROZEN,
                message=f"Destination account '{destination_account_id}' is frozen",
            )
        if dest_acc.status != AccountStatus.ACTIVE:
            return OperationResult(
                success=False,
                error_code=ErrorCode.ACCOUNT_INACTIVE,
                message=f"Destination account '{destination_account_id}' is inactive",
            )

        # Step 7: Currency Compatibility Check
        if source_acc.currency != norm_currency or dest_acc.currency != norm_currency:
            return OperationResult(
                success=False,
                error_code=ErrorCode.CURRENCY_MISMATCH,
                message=f"Currency mismatch: source is {source_acc.currency}, dest is {dest_acc.currency}, requested {norm_currency}",
            )

        # Step 8: Balance Check (Sufficient Funds)
        if source_acc.balance < norm_amount:
            return OperationResult(
                success=False,
                error_code=ErrorCode.INSUFFICIENT_FUNDS,
                message=f"Insufficient balance in account '{source_account_id}': available {source_acc.balance}, requested {norm_amount}",
            )

        # Step 9: Controlled Failure Injection (Pre-Commit)
        if self._failure_mode == FailureMode.PRE_COMMIT_FAILURE:
            # Operation is aborted before any state mutation; NOT cached for idempotency
            return OperationResult(
                success=False,
                error_code=ErrorCode.SIMULATED_FAILURE,
                message="Simulated pre-commit failure injected: operation aborted before state commit",
            )

        # Step 10: State Commit (Atomic In-Memory Mutation)
        source_acc.balance -= norm_amount
        dest_acc.balance += norm_amount

        tx_id = self._generate_tx_id()
        timestamp = self._clock.now_iso()
        self._clock.tick(1)

        tx = Transaction(
            transaction_id=tx_id,
            transaction_type=TransactionType.TRANSFER,
            source_account_id=source_account_id,
            destination_account_id=destination_account_id,
            beneficiary_id=beneficiary_id,
            amount=norm_amount,
            currency=norm_currency,
            status=TransactionStatus.POSTED,
            timestamp=timestamp,
            reference=idempotency_key,
        )
        self._transactions[tx_id] = tx

        result = OperationResult(
            success=True,
            error_code=ErrorCode.SUCCESS,
            message="Transfer completed successfully",
            data=tx,
            transaction_id=tx_id,
        )

        # Cache in idempotency store only on success
        if idempotency_key is not None and fingerprint is not None:
            self._idempotency_store[idempotency_key] = (fingerprint, result)

        return result
