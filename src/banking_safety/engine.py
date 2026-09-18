"""
Deterministic Transaction Safety Engine.

Orchestrates idempotency replay short-circuiting, currency enforcement,
limit evaluations, and step-up approval verification in strict deterministic order.
"""

from typing import Optional

from banking_safety.approval import SimulatedStepUpApprovalService, StepUpApproval
from banking_safety.config import TransactionSafetyConfig
from banking_safety.contracts import SafetyDecision, SafetyReasonCode, SafetyResult
from banking_safety.idempotency import AuthoritativeIdempotencyStore
from banking_safety.limits import TransactionLimitEvaluator
from banking_safety.request import TransactionRequest
from banking_security.context import AuthContext
from banking_simulator.clock import SimulatedClock
from banking_simulator.simulator import BankingSimulator


class TransactionSafetyEngine:
    """
    Evaluates whether an authorized transaction is safe, compliant with limits, and approved.
    Fail-closed by default with zero LLM reasoning.
    """

    def __init__(
        self,
        clock: Optional[SimulatedClock] = None,
        config: Optional[TransactionSafetyConfig] = None,
        idempotency_store: Optional[AuthoritativeIdempotencyStore] = None,
        approval_service: Optional[SimulatedStepUpApprovalService] = None,
        limit_evaluator: Optional[TransactionLimitEvaluator] = None,
    ):
        self._clock = clock or SimulatedClock()
        self._config = config or TransactionSafetyConfig()
        self._idempotency_store = idempotency_store or AuthoritativeIdempotencyStore()
        self._approval_service = approval_service or SimulatedStepUpApprovalService(clock=self._clock)
        self._limit_evaluator = limit_evaluator or TransactionLimitEvaluator(clock=self._clock)

    @property
    def clock(self) -> SimulatedClock:
        return self._clock

    @property
    def config(self) -> TransactionSafetyConfig:
        return self._config

    @property
    def idempotency_store(self) -> AuthoritativeIdempotencyStore:
        return self._idempotency_store

    @property
    def approval_service(self) -> SimulatedStepUpApprovalService:
        return self._approval_service

    @property
    def limit_evaluator(self) -> TransactionLimitEvaluator:
        return self._limit_evaluator

    def evaluate(
        self,
        request: TransactionRequest,
        auth_context: AuthContext,
        simulator: BankingSimulator,
        approval: Optional[StepUpApproval] = None,
    ) -> SafetyResult:
        """
        Evaluate an authorized transaction request against deterministic safety policies.

        Evaluation Order:
        1. Mandatory Idempotency Key Validation
        2. Authoritative Idempotency Store Lookup (Replay Short-Circuit vs Conflict)
        3. Currency & Financial Limits (Currency match, Per-Tx, Daily Cumulative, Velocity)
        4. Step-Up Approval Check (Trigger threshold, Principal binding, Fingerprint match)
        """
        now_iso = self._clock.now_iso()
        fingerprint = request.compute_fingerprint()
        principal_id = auth_context.principal_id or ""

        # ----------------------------------------------------------------------
        # 1. Mandatory Idempotency Key Validation
        # ----------------------------------------------------------------------
        if not request.idempotency_key or not request.idempotency_key.strip():
            return SafetyResult(
                decision=SafetyDecision.DENY,
                reason_code=SafetyReasonCode.MISSING_IDEMPOTENCY_KEY,
                message="Every state-changing transaction requires a mandatory, non-empty idempotency key.",
                fingerprint=fingerprint,
                evaluated_at=now_iso,
            )

        # ----------------------------------------------------------------------
        # 2. Idempotency Check (Scoped to principal_id)
        # ----------------------------------------------------------------------
        cached_result, idempotency_status = self._idempotency_store.check(
            principal_id=principal_id,
            idempotency_key=request.idempotency_key,
            fingerprint=fingerprint,
        )

        if idempotency_status == SafetyReasonCode.IDEMPOTENCY_REPLAY:
            # Short-circuit: An identical replay of an already-committed transaction
            # MUST NOT re-evaluate limits (which might now be exhausted) or step-up.
            return SafetyResult(
                decision=SafetyDecision.ALLOW,
                reason_code=SafetyReasonCode.IDEMPOTENCY_REPLAY,
                message="Identical idempotency replay detected: returning cached transaction outcome.",
                fingerprint=fingerprint,
                evaluated_at=now_iso,
            )

        if idempotency_status == SafetyReasonCode.IDEMPOTENCY_CONFLICT:
            return SafetyResult(
                decision=SafetyDecision.DENY,
                reason_code=SafetyReasonCode.IDEMPOTENCY_CONFLICT,
                message=(
                    f"Idempotency conflict: key '{request.idempotency_key}' has already "
                    f"been used by principal '{principal_id}' with different transaction parameters."
                ),
                fingerprint=fingerprint,
                evaluated_at=now_iso,
            )

        # ----------------------------------------------------------------------
        # 3. Currency & Financial Limit Checks
        # ----------------------------------------------------------------------
        limit_result = self._limit_evaluator.evaluate_limits(
            request=request,
            simulator=simulator,
            config=self._config,
        )
        if limit_result.decision == SafetyDecision.DENY:
            return limit_result

        # ----------------------------------------------------------------------
        # 4. Step-Up Approval Evaluation
        # ----------------------------------------------------------------------
        if request.amount >= self._config.step_up_threshold:
            if approval is None:
                return SafetyResult(
                    decision=SafetyDecision.STEP_UP_REQUIRED,
                    reason_code=SafetyReasonCode.STEP_UP_REQUIRED,
                    message=(
                        f"Transfer amount {request.amount} {request.currency} meets or exceeds "
                        f"the step-up threshold of {self._config.step_up_threshold} {self._config.currency}. "
                        f"Simulated step-up approval is required."
                    ),
                    fingerprint=fingerprint,
                    evaluated_at=now_iso,
                    metadata={"step_up_threshold": str(self._config.step_up_threshold)},
                )

            # Verify the supplied approval artifact
            is_valid, reason_code, message = self._approval_service.verify_approval(
                approval=approval,
                request=request,
                auth_context=auth_context,
            )
            if not is_valid:
                return SafetyResult(
                    decision=SafetyDecision.DENY,
                    reason_code=reason_code,
                    message=f"Step-up approval rejected: {message}",
                    fingerprint=fingerprint,
                    evaluated_at=now_iso,
                )

        # All safety gates passed
        return SafetyResult(
            decision=SafetyDecision.ALLOW,
            reason_code=SafetyReasonCode.SAFETY_ALLOWED,
            message="Transaction parameters passed all safety, limit, and approval evaluations.",
            fingerprint=fingerprint,
            evaluated_at=now_iso,
        )
