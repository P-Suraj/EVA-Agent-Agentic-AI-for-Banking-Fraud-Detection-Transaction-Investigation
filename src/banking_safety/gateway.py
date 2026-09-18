"""
Secure Execution Gateway Facade.

Composes:
- Layer 1: Authentication (SimulatedSessionManager)
- Layer 2: Authorization (DeterministicPolicyEngine)
- Layer 3: Transaction Safety & Deterministic Gate (TransactionSafetyEngine)
- Layer 4: Banking Simulator State Machine (BankingSimulator)

Guarantees that state-changing mutations never reach the simulator unless all
three preceding gates return ALLOW.
"""

from decimal import Decimal
from typing import Any, Optional

from banking_safety.approval import StepUpApproval
from banking_safety.contracts import (
    ExecutionGateResult,
    GateStage,
    SafetyDecision,
    SafetyReasonCode,
)
from banking_safety.engine import TransactionSafetyEngine
from banking_safety.request import TransactionRequest
from banking_security.actions import BankingAction, ResourceTarget, ResourceType
from banking_security.context import SimulatedSessionManager
from banking_security.contracts import PolicyDecision
from banking_security.engine import DeterministicPolicyEngine
from banking_simulator.contracts import ErrorCode
from banking_simulator.models import Account, Beneficiary, Card, Transaction
from banking_simulator.simulator import BankingSimulator


class SecureExecutionGateway:
    """
    Authoritative, safety-gated execution gateway wrapping BankingSimulator.
    """

    def __init__(
        self,
        simulator: BankingSimulator,
        session_manager: Optional[SimulatedSessionManager] = None,
        policy_engine: Optional[DeterministicPolicyEngine] = None,
        safety_engine: Optional[TransactionSafetyEngine] = None,
    ):
        self._simulator = simulator
        self._session_manager = session_manager or SimulatedSessionManager(simulator)
        self._policy_engine = policy_engine or DeterministicPolicyEngine()
        self._safety_engine = safety_engine or TransactionSafetyEngine()

    @property
    def simulator(self) -> BankingSimulator:
        return self._simulator

    @property
    def session_manager(self) -> SimulatedSessionManager:
        return self._session_manager

    @property
    def policy_engine(self) -> DeterministicPolicyEngine:
        return self._policy_engine

    @property
    def safety_engine(self) -> TransactionSafetyEngine:
        return self._safety_engine

    # --------------------------------------------------------------------------
    # Read Operations (Gated by Layer 1 Authentication & Layer 2 Authorization)
    # --------------------------------------------------------------------------

    def get_account(self, session_token: Optional[str], account_id: str) -> ExecutionGateResult[Account]:
        auth_context = self._session_manager.authenticate(session_token)
        target = ResourceTarget(resource_type=ResourceType.ACCOUNT, resource_id=account_id)
        policy_res = self._policy_engine.evaluate(auth_context, BankingAction.READ_ACCOUNT, target, self._simulator)

        if policy_res.decision == PolicyDecision.DENY:
            return ExecutionGateResult(
                success=False,
                error_code=ErrorCode.PERMISSION_DENIED,
                message=f"Authorization denied: {policy_res.message}",
                policy_result=policy_res,
                gate_stage=GateStage.AUTHORIZATION,
            )

        account = self._simulator.get_account(account_id)
        return ExecutionGateResult(
            success=True,
            error_code=ErrorCode.SUCCESS,
            message="Account retrieved successfully",
            data=account,
            policy_result=policy_res,
            gate_stage=GateStage.SIMULATOR_EXECUTION,
        )

    def get_balance(self, session_token: Optional[str], account_id: str) -> ExecutionGateResult[Decimal]:
        auth_context = self._session_manager.authenticate(session_token)
        target = ResourceTarget(resource_type=ResourceType.ACCOUNT, resource_id=account_id)
        policy_res = self._policy_engine.evaluate(auth_context, BankingAction.READ_BALANCE, target, self._simulator)

        if policy_res.decision == PolicyDecision.DENY:
            return ExecutionGateResult(
                success=False,
                error_code=ErrorCode.PERMISSION_DENIED,
                message=f"Authorization denied: {policy_res.message}",
                policy_result=policy_res,
                gate_stage=GateStage.AUTHORIZATION,
            )

        balance = self._simulator.get_balance(account_id)
        return ExecutionGateResult(
            success=True,
            error_code=ErrorCode.SUCCESS,
            message="Balance retrieved successfully",
            data=balance,
            policy_result=policy_res,
            gate_stage=GateStage.SIMULATOR_EXECUTION,
        )

    def get_transactions(self, session_token: Optional[str], account_id: str) -> ExecutionGateResult[list[Transaction]]:
        auth_context = self._session_manager.authenticate(session_token)
        target = ResourceTarget(resource_type=ResourceType.ACCOUNT, resource_id=account_id)
        policy_res = self._policy_engine.evaluate(auth_context, BankingAction.READ_TRANSACTIONS, target, self._simulator)

        if policy_res.decision == PolicyDecision.DENY:
            return ExecutionGateResult(
                success=False,
                error_code=ErrorCode.PERMISSION_DENIED,
                message=f"Authorization denied: {policy_res.message}",
                policy_result=policy_res,
                gate_stage=GateStage.AUTHORIZATION,
            )

        transactions = self._simulator.get_transactions(account_id)
        return ExecutionGateResult(
            success=True,
            error_code=ErrorCode.SUCCESS,
            message="Transactions retrieved successfully",
            data=transactions,
            policy_result=policy_res,
            gate_stage=GateStage.SIMULATOR_EXECUTION,
        )

    def get_beneficiary(self, session_token: Optional[str], beneficiary_id: str) -> ExecutionGateResult[Beneficiary]:
        auth_context = self._session_manager.authenticate(session_token)
        target = ResourceTarget(resource_type=ResourceType.BENEFICIARY, resource_id=beneficiary_id)
        policy_res = self._policy_engine.evaluate(auth_context, BankingAction.READ_BENEFICIARY, target, self._simulator)

        if policy_res.decision == PolicyDecision.DENY:
            return ExecutionGateResult(
                success=False,
                error_code=ErrorCode.PERMISSION_DENIED,
                message=f"Authorization denied: {policy_res.message}",
                policy_result=policy_res,
                gate_stage=GateStage.AUTHORIZATION,
            )

        ben = self._simulator.get_beneficiary(auth_context.principal_id or "", beneficiary_id)
        return ExecutionGateResult(
            success=True,
            error_code=ErrorCode.SUCCESS,
            message="Beneficiary retrieved successfully",
            data=ben,
            policy_result=policy_res,
            gate_stage=GateStage.SIMULATOR_EXECUTION,
        )

    def get_card(self, session_token: Optional[str], card_id: str) -> ExecutionGateResult[Card]:
        auth_context = self._session_manager.authenticate(session_token)
        target = ResourceTarget(resource_type=ResourceType.CARD, resource_id=card_id)
        policy_res = self._policy_engine.evaluate(auth_context, BankingAction.READ_CARD, target, self._simulator)

        if policy_res.decision == PolicyDecision.DENY:
            return ExecutionGateResult(
                success=False,
                error_code=ErrorCode.PERMISSION_DENIED,
                message=f"Authorization denied: {policy_res.message}",
                policy_result=policy_res,
                gate_stage=GateStage.AUTHORIZATION,
            )

        card = self._simulator.get_card(card_id)
        return ExecutionGateResult(
            success=True,
            error_code=ErrorCode.SUCCESS,
            message="Card retrieved successfully",
            data=card,
            policy_result=policy_res,
            gate_stage=GateStage.SIMULATOR_EXECUTION,
        )

    # --------------------------------------------------------------------------
    # Card Operations
    # --------------------------------------------------------------------------

    def freeze_card(self, session_token: Optional[str], card_id: str) -> ExecutionGateResult[Card]:
        auth_context = self._session_manager.authenticate(session_token)
        target = ResourceTarget(resource_type=ResourceType.CARD, resource_id=card_id)
        policy_res = self._policy_engine.evaluate(auth_context, BankingAction.FREEZE_CARD, target, self._simulator)

        if policy_res.decision == PolicyDecision.DENY:
            return ExecutionGateResult(
                success=False,
                error_code=ErrorCode.PERMISSION_DENIED,
                message=f"Authorization denied: {policy_res.message}",
                policy_result=policy_res,
                gate_stage=GateStage.AUTHORIZATION,
            )

        sim_res = self._simulator.freeze_card(card_id)
        return ExecutionGateResult(
            success=sim_res.success,
            error_code=sim_res.error_code,
            message=sim_res.message,
            data=sim_res.data,
            policy_result=policy_res,
            gate_stage=GateStage.SIMULATOR_EXECUTION,
        )

    # --------------------------------------------------------------------------
    # State-Changing Transaction Execution (4-Layer Gated Pipeline)
    # --------------------------------------------------------------------------

    def execute_transaction(
        self,
        session_token: Optional[str],
        request: TransactionRequest,
        approval: Optional[StepUpApproval] = None,
    ) -> ExecutionGateResult[Transaction]:
        """
        Execute an authorized, safety-evaluated, and approved transaction.

        Guarantees:
        - Layer 1: Authentication failure -> Simulator mutation count = 0.
        - Layer 2: Authorization failure -> Simulator mutation count = 0.
        - Layer 3: Safety / Limit / Step-up failure -> Simulator mutation count = 0.
        - Idempotency replay -> Simulator mutation count = 0 (returns cached result).
        - Idempotency conflict -> Simulator mutation count = 0.
        - Simulator failure (e.g. INSUFFICIENT_FUNDS) -> Zero balance mutation;
          idempotency key NOT committed; approval token NOT consumed (allows retry).
        - Simulator success (POSTED) -> Key committed; approval consumed.
        """
        # ----------------------------------------------------------------------
        # Step 1: Structural Request Contract Check
        # ----------------------------------------------------------------------
        if not isinstance(request, TransactionRequest):
            return ExecutionGateResult(
                success=False,
                error_code=SafetyReasonCode.INVALID_TRANSACTION_REQUEST,
                message="Request must be a valid TransactionRequest instance.",
                gate_stage=GateStage.TRANSACTION_SAFETY,
            )

        # ----------------------------------------------------------------------
        # Step 2: Layer 1 Authentication Gate
        # ----------------------------------------------------------------------
        auth_context = self._session_manager.authenticate(session_token)
        if not auth_context.authenticated or not auth_context.principal_id:
            return ExecutionGateResult(
                success=False,
                error_code=ErrorCode.PERMISSION_DENIED,
                message="Authentication required: valid session token required.",
                gate_stage=GateStage.AUTHENTICATION,
            )

        principal_id = auth_context.principal_id

        # ----------------------------------------------------------------------
        # Step 3: Layer 2 Authorization Gate
        # ----------------------------------------------------------------------
        target = ResourceTarget(
            resource_type=ResourceType.ACCOUNT,
            resource_id=request.source_account_id,
            secondary_resource_id=request.target_reference,
        )
        policy_res = self._policy_engine.evaluate(
            auth_context=auth_context,
            action=request.operation_type,
            resource_target=target,
            simulator=self._simulator,
        )

        if policy_res.decision == PolicyDecision.DENY:
            return ExecutionGateResult(
                success=False,
                error_code=ErrorCode.PERMISSION_DENIED,
                message=f"Authorization denied: {policy_res.message}",
                policy_result=policy_res,
                gate_stage=GateStage.AUTHORIZATION,
            )

        # ----------------------------------------------------------------------
        # Step 4: Layer 3 Transaction Safety & Gate
        # ----------------------------------------------------------------------
        safety_res = self._safety_engine.evaluate(
            request=request,
            auth_context=auth_context,
            simulator=self._simulator,
            approval=approval,
        )

        # 4a. Idempotency Replay Short-Circuit
        if safety_res.reason_code == SafetyReasonCode.IDEMPOTENCY_REPLAY:
            cached_result, _ = self._safety_engine.idempotency_store.check(
                principal_id=principal_id,
                idempotency_key=request.idempotency_key,
                fingerprint=request.compute_fingerprint(),
            )
            if cached_result:
                # Return the cached execution result directly; simulator is NEVER invoked a second time
                return ExecutionGateResult(
                    success=cached_result.success,
                    error_code=cached_result.error_code,
                    message=cached_result.message,
                    data=cached_result.data,
                    transaction_id=cached_result.transaction_id,
                    policy_result=policy_res,
                    safety_result=safety_res,
                    cached_replay=True,
                    gate_stage=GateStage.TRANSACTION_SAFETY,
                )

        # 4b. Step-Up Approval Required
        if safety_res.decision == SafetyDecision.STEP_UP_REQUIRED:
            return ExecutionGateResult(
                success=False,
                error_code=SafetyReasonCode.STEP_UP_REQUIRED,
                message=safety_res.message,
                policy_result=policy_res,
                safety_result=safety_res,
                gate_stage=GateStage.TRANSACTION_SAFETY,
            )

        # 4c. Safety Policy Denial (Limits exceeded, currency unsupported, idempotency conflict, or approval tampered)
        if safety_res.decision == SafetyDecision.DENY:
            return ExecutionGateResult(
                success=False,
                error_code=safety_res.reason_code,
                message=safety_res.message,
                policy_result=policy_res,
                safety_result=safety_res,
                gate_stage=GateStage.TRANSACTION_SAFETY,
            )

        # ----------------------------------------------------------------------
        # Step 5: Layer 4 Simulator Execution
        # (Reachable ONLY after Layers 1, 2, and 3 have evaluated to ALLOW)
        # ----------------------------------------------------------------------
        scoped_idempotency_key = f"{principal_id}:{request.idempotency_key}"
        try:
            if request.operation_type == BankingAction.TRANSFER:
                sim_res = self._simulator.transfer(
                    source_account_id=request.source_account_id,
                    destination_account_id=request.destination_account_id or "",
                    amount=request.amount,
                    currency=request.currency,
                    idempotency_key=scoped_idempotency_key,
                )
            elif request.operation_type == BankingAction.TRANSFER_TO_BENEFICIARY:
                sim_res = self._simulator.transfer_to_beneficiary(
                    owner_user_id=principal_id,
                    source_account_id=request.source_account_id,
                    beneficiary_id=request.beneficiary_id or "",
                    amount=request.amount,
                    currency=request.currency,
                    idempotency_key=scoped_idempotency_key,
                )
            else:
                return ExecutionGateResult(
                    success=False,
                    error_code=SafetyReasonCode.FAIL_CLOSED_ERROR,
                    message=f"Unsupported transaction operation type '{request.operation_type}'.",
                    policy_result=policy_res,
                    safety_result=safety_res,
                    gate_stage=GateStage.SIMULATOR_EXECUTION,
                )
        except Exception as exc:
            # Unexpected execution failure: fail closed, do NOT commit key, do NOT consume approval
            return ExecutionGateResult(
                success=False,
                error_code=SafetyReasonCode.FAIL_CLOSED_ERROR,
                message=f"Unexpected simulator execution failure: {str(exc)}",
                policy_result=policy_res,
                safety_result=safety_res,
                gate_stage=GateStage.SIMULATOR_EXECUTION,
            )

        # ----------------------------------------------------------------------
        # Step 6: Post-Execution Lifecycle
        # ----------------------------------------------------------------------
        if sim_res.success:
            # State committed in simulator (POSTED)
            result = ExecutionGateResult(
                success=True,
                error_code=sim_res.error_code,
                message=sim_res.message,
                data=sim_res.data,
                transaction_id=sim_res.transaction_id,
                policy_result=policy_res,
                safety_result=safety_res,
                cached_replay=False,
                gate_stage=GateStage.SIMULATOR_EXECUTION,
            )

            # 1. Commit to authoritative idempotency store
            self._safety_engine.idempotency_store.commit(
                principal_id=principal_id,
                idempotency_key=request.idempotency_key,
                fingerprint=request.compute_fingerprint(),
                result=result,
            )

            # 2. Consume step-up approval token if one was used
            if approval and hasattr(approval, "approval_id"):
                self._safety_engine.approval_service.consume_approval(approval.approval_id)

            return result
        else:
            # Known simulator business rejection (INSUFFICIENT_FUNDS, ACCOUNT_FROZEN, SIMULATED_FAILURE)
            # Crucial invariant:
            # - Idempotency key is NOT committed (caller can retry once funds/state are resolved)
            # - Step-up approval token is NOT consumed (remains reusable for valid retry)
            return ExecutionGateResult(
                success=False,
                error_code=sim_res.error_code,
                message=sim_res.message,
                data=sim_res.data,
                transaction_id=None,
                policy_result=policy_res,
                safety_result=safety_res,
                cached_replay=False,
                gate_stage=GateStage.SIMULATOR_EXECUTION,
            )
