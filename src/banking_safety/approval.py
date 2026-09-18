"""
Simulated Step-Up Approval Provider and Models for Transaction Safety.

Establishes a trusted boundary for simulating external MFA / approval events.
Callers and future agents cannot manufacture valid approvals or self-assert approval=True.
"""

from datetime import datetime, timedelta
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from banking_safety.contracts import SafetyReasonCode
from banking_safety.request import TransactionRequest
from banking_security.context import AuthContext
from banking_simulator.clock import SimulatedClock


class StepUpApproval(BaseModel):
    """
    Sealed, immutable step-up approval artifact issued by a trusted simulated provider.
    Bound strictly to principal_id, exact transaction fingerprint, and expiration.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_id: str = Field(..., min_length=1, description="Unique approval identifier")
    principal_id: str = Field(..., min_length=1, description="Authenticated principal this approval was issued for")
    transaction_fingerprint: str = Field(
        ..., min_length=1, description="Exact SHA-256 transaction fingerprint approved"
    )
    issued_at: str = Field(..., description="ISO-8601 timestamp when approval was issued")
    expires_at: Optional[str] = Field(default=None, description="ISO-8601 timestamp when approval expires")


class SimulatedStepUpApprovalService:
    """
    Authoritative provider for issuing and verifying simulated step-up approvals.

    Trust Boundary:
    - Issue (`issue_approval`) is a trusted provider operation simulating an out-of-band approval.
      Untrusted agents/callers cannot invoke this to self-authorize.
    - Verify (`verify_approval`) validates token integrity and fingerprint match before execution.
    - Consume (`consume_approval`) marks the token as used ONLY after successful simulator commit.
    """

    def __init__(self, clock: Optional[SimulatedClock] = None):
        self._clock = clock or SimulatedClock()
        self._issued_approvals: dict[str, StepUpApproval] = {}
        self._consumed_approval_ids: set[str] = set()
        self._counter: int = 0

    @property
    def clock(self) -> SimulatedClock:
        return self._clock

    def issue_approval(
        self,
        principal_id: str,
        request: TransactionRequest,
        valid_duration_seconds: int = 300,
    ) -> StepUpApproval:
        """
        Trusted simulated approval provider issuance.
        Strictly binds the approval to the caller's principal_id and request fingerprint.
        """
        self._counter += 1
        approval_id = f"appr_{self._counter:04d}"
        now_iso = self._clock.now_iso()
        now_dt = datetime.fromisoformat(now_iso)
        expires_dt = now_dt + timedelta(seconds=valid_duration_seconds)
        expires_at = expires_dt.isoformat()

        fingerprint = request.compute_fingerprint()

        approval = StepUpApproval(
            approval_id=approval_id,
            principal_id=principal_id,
            transaction_fingerprint=fingerprint,
            issued_at=now_iso,
            expires_at=expires_at,
        )
        self._issued_approvals[approval_id] = approval
        return approval

    def verify_approval(
        self,
        approval: Any,
        request: TransactionRequest,
        auth_context: AuthContext,
    ) -> tuple[bool, SafetyReasonCode, str]:
        """
        Verify the integrity, principal binding, fingerprint match, and expiration of an approval.
        Does NOT consume the approval (consumption occurs only post-commit).
        """
        # 1. Type validation
        if not isinstance(approval, StepUpApproval):
            return (
                False,
                SafetyReasonCode.UNTRUSTED_APPROVAL,
                "Approval token must be an instance of StepUpApproval issued by the trusted approval service.",
            )

        # 2. Registry existence (prevents caller from fabricating an approval object)
        if approval.approval_id not in self._issued_approvals:
            return (
                False,
                SafetyReasonCode.UNTRUSTED_APPROVAL,
                f"Approval '{approval.approval_id}' was not issued by the trusted approval provider.",
            )

        # 3. Consumption check
        if approval.approval_id in self._consumed_approval_ids:
            return (
                False,
                SafetyReasonCode.APPROVAL_ALREADY_USED,
                f"Approval '{approval.approval_id}' has already been consumed and cannot be reused.",
            )

        # 4. Principal identity binding check
        if approval.principal_id != auth_context.principal_id:
            return (
                False,
                SafetyReasonCode.APPROVAL_MISMATCH,
                (
                    f"Approval principal '{approval.principal_id}' does not match "
                    f"authenticated caller principal '{auth_context.principal_id}'."
                ),
            )

        # 5. Exact transaction fingerprint binding check
        current_fingerprint = request.compute_fingerprint()
        if approval.transaction_fingerprint != current_fingerprint:
            return (
                False,
                SafetyReasonCode.APPROVAL_MISMATCH,
                (
                    f"Approval fingerprint mismatch: approval was issued for fingerprint "
                    f"'{approval.transaction_fingerprint}', but request fingerprint is '{current_fingerprint}'."
                ),
            )

        # 6. Expiration check using public clock API
        if approval.expires_at:
            now_dt = datetime.fromisoformat(self._clock.now_iso())
            expires_dt = datetime.fromisoformat(approval.expires_at)
            if now_dt > expires_dt:
                return (
                    False,
                    SafetyReasonCode.APPROVAL_EXPIRED,
                    f"Approval '{approval.approval_id}' expired at {approval.expires_at} (current time: {self._clock.now_iso()}).",
                )

        return True, SafetyReasonCode.SAFETY_ALLOWED, "Approval verified successfully."

    def consume_approval(self, approval_id: str) -> None:
        """
        Mark an approval as permanently consumed.
        Must ONLY be called after state mutation has successfully committed (POSTED).
        """
        self._consumed_approval_ids.add(approval_id)

    def is_consumed(self, approval_id: str) -> bool:
        return approval_id in self._consumed_approval_ids
