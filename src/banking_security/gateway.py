"""
Secure Banking Gateway Facade.

Enforces deterministic authentication and authorization policies prior to
dispatching operations to the BankingSimulator.
"""

from decimal import Decimal
from typing import Any, Optional

from banking_security.actions import BankingAction, ResourceTarget, ResourceType
from banking_security.context import SimulatedSessionManager
from banking_security.contracts import PolicyDecision
from banking_security.engine import DeterministicPolicyEngine
from banking_simulator.contracts import ErrorCode, OperationResult
from banking_simulator.models import Account, Beneficiary, Card, Transaction
from banking_simulator.simulator import BankingSimulator


class SecureBankingGateway:
    """
    Authorized facade wrapping the frozen BankingSimulator.
    Every call requires a valid simulated session token. Unauthorized calls are
    rejected immediately without invoking simulator operations or mutating state.
    """

    def __init__(
        self,
        simulator: BankingSimulator,
        session_manager: Optional[SimulatedSessionManager] = None,
        policy_engine: Optional[DeterministicPolicyEngine] = None,
    ):
        self._simulator = simulator
        self._session_manager = session_manager or SimulatedSessionManager(simulator)
        self._policy_engine = policy_engine or DeterministicPolicyEngine()

    @property
    def simulator(self) -> BankingSimulator:
        """Reference to underlying simulator for test inspection."""
        return self._simulator

    @property
    def session_manager(self) -> SimulatedSessionManager:
        return self._session_manager

    # --------------------------------------------------------------------------
    # Read Operations
    # --------------------------------------------------------------------------

    def get_account(self, session_token: Optional[str], account_id: str) -> OperationResult[Account]:
        auth_context = self._session_manager.authenticate(session_token)
        target = ResourceTarget(resource_type=ResourceType.ACCOUNT, resource_id=account_id)
        policy_res = self._policy_engine.evaluate(auth_context, BankingAction.READ_ACCOUNT, target, self._simulator)

        if policy_res.decision == PolicyDecision.DENY:
            return OperationResult(
                success=False,
                error_code=ErrorCode.PERMISSION_DENIED,
                message=f"Authorization denied: {policy_res.message}",
            )

        account = self._simulator.get_account(account_id)
        return OperationResult(
            success=True,
            error_code=ErrorCode.SUCCESS,
            message="Account retrieved successfully",
            data=account,
        )

    def get_balance(self, session_token: Optional[str], account_id: str) -> OperationResult[Decimal]:
        auth_context = self._session_manager.authenticate(session_token)
        target = ResourceTarget(resource_type=ResourceType.ACCOUNT, resource_id=account_id)
        policy_res = self._policy_engine.evaluate(auth_context, BankingAction.READ_BALANCE, target, self._simulator)

        if policy_res.decision == PolicyDecision.DENY:
            return OperationResult(
                success=False,
                error_code=ErrorCode.PERMISSION_DENIED,
                message=f"Authorization denied: {policy_res.message}",
            )

        balance = self._simulator.get_balance(account_id)
        return OperationResult(
            success=True,
            error_code=ErrorCode.SUCCESS,
            message="Balance retrieved successfully",
            data=balance,
        )

    def get_transactions(self, session_token: Optional[str], account_id: str) -> OperationResult[list[Transaction]]:
        auth_context = self._session_manager.authenticate(session_token)
        target = ResourceTarget(resource_type=ResourceType.ACCOUNT, resource_id=account_id)
        policy_res = self._policy_engine.evaluate(auth_context, BankingAction.READ_TRANSACTIONS, target, self._simulator)

        if policy_res.decision == PolicyDecision.DENY:
            return OperationResult(
                success=False,
                error_code=ErrorCode.PERMISSION_DENIED,
                message=f"Authorization denied: {policy_res.message}",
            )

        transactions = self._simulator.get_transactions(account_id)
        return OperationResult(
            success=True,
            error_code=ErrorCode.SUCCESS,
            message="Transactions retrieved successfully",
            data=transactions,
        )

    def get_beneficiary(self, session_token: Optional[str], beneficiary_id: str) -> OperationResult[Beneficiary]:
        auth_context = self._session_manager.authenticate(session_token)
        target = ResourceTarget(resource_type=ResourceType.BENEFICIARY, resource_id=beneficiary_id)
        policy_res = self._policy_engine.evaluate(auth_context, BankingAction.READ_BENEFICIARY, target, self._simulator)

        if policy_res.decision == PolicyDecision.DENY:
            return OperationResult(
                success=False,
                error_code=ErrorCode.PERMISSION_DENIED,
                message=f"Authorization denied: {policy_res.message}",
            )

        ben = self._simulator.get_beneficiary(auth_context.principal_id or "", beneficiary_id)
        return OperationResult(
            success=True,
            error_code=ErrorCode.SUCCESS,
            message="Beneficiary retrieved successfully",
            data=ben,
        )

    def get_card(self, session_token: Optional[str], card_id: str) -> OperationResult[Card]:
        auth_context = self._session_manager.authenticate(session_token)
        target = ResourceTarget(resource_type=ResourceType.CARD, resource_id=card_id)
        policy_res = self._policy_engine.evaluate(auth_context, BankingAction.READ_CARD, target, self._simulator)

        if policy_res.decision == PolicyDecision.DENY:
            return OperationResult(
                success=False,
                error_code=ErrorCode.PERMISSION_DENIED,
                message=f"Authorization denied: {policy_res.message}",
            )

        card = self._simulator.get_card(card_id)
        return OperationResult(
            success=True,
            error_code=ErrorCode.SUCCESS,
            message="Card retrieved successfully",
            data=card,
        )

    # --------------------------------------------------------------------------
    # Card Operations
    # --------------------------------------------------------------------------

    def freeze_card(self, session_token: Optional[str], card_id: str) -> OperationResult[Card]:
        auth_context = self._session_manager.authenticate(session_token)
        target = ResourceTarget(resource_type=ResourceType.CARD, resource_id=card_id)
        policy_res = self._policy_engine.evaluate(auth_context, BankingAction.FREEZE_CARD, target, self._simulator)

        if policy_res.decision == PolicyDecision.DENY:
            return OperationResult(
                success=False,
                error_code=ErrorCode.PERMISSION_DENIED,
                message=f"Authorization denied: {policy_res.message}",
            )

        return self._simulator.freeze_card(card_id)

    # --------------------------------------------------------------------------
    # Transfer Operations
    # --------------------------------------------------------------------------

    def transfer(
        self,
        session_token: Optional[str],
        source_account_id: str,
        destination_account_id: str,
        amount: Any,
        currency: str = "INR",
        idempotency_key: Optional[str] = None,
    ) -> OperationResult[Transaction]:
        """
        Execute an authorized direct transfer.
        Sender authorization requires source account ownership.
        Destination account ownership is NOT required (peer-to-peer target).
        """
        auth_context = self._session_manager.authenticate(session_token)
        target = ResourceTarget(
            resource_type=ResourceType.ACCOUNT,
            resource_id=source_account_id,
            secondary_resource_id=destination_account_id,
        )
        policy_res = self._policy_engine.evaluate(auth_context, BankingAction.TRANSFER, target, self._simulator)

        if policy_res.decision == PolicyDecision.DENY:
            return OperationResult(
                success=False,
                error_code=ErrorCode.PERMISSION_DENIED,
                message=f"Authorization denied: {policy_res.message}",
            )

        # Authorization passed; simulator evaluates business & transaction policy
        return self._simulator.transfer(
            source_account_id=source_account_id,
            destination_account_id=destination_account_id,
            amount=amount,
            currency=currency,
            idempotency_key=idempotency_key,
        )

    def transfer_to_beneficiary(
        self,
        session_token: Optional[str],
        source_account_id: str,
        beneficiary_id: str,
        amount: Any,
        currency: str = "INR",
        idempotency_key: Optional[str] = None,
    ) -> OperationResult[Transaction]:
        """
        Execute an authorized transfer to a verified beneficiary.
        Requires ownership of source account AND ownership of verified beneficiary.
        """
        auth_context = self._session_manager.authenticate(session_token)
        target = ResourceTarget(
            resource_type=ResourceType.ACCOUNT,
            resource_id=source_account_id,
            secondary_resource_id=beneficiary_id,
        )
        policy_res = self._policy_engine.evaluate(
            auth_context, BankingAction.TRANSFER_TO_BENEFICIARY, target, self._simulator
        )

        if policy_res.decision == PolicyDecision.DENY:
            return OperationResult(
                success=False,
                error_code=ErrorCode.PERMISSION_DENIED,
                message=f"Authorization denied: {policy_res.message}",
            )

        # Authorization passed; invoke simulator with verified caller identity
        return self._simulator.transfer_to_beneficiary(
            owner_user_id=auth_context.principal_id or "",
            source_account_id=source_account_id,
            beneficiary_id=beneficiary_id,
            amount=amount,
            currency=currency,
            idempotency_key=idempotency_key,
        )
