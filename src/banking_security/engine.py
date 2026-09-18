"""
Deterministic Policy Engine for Banking Security.

Implements pure, deterministic authorization evaluation separating identity validation,
ownership checks, and business transaction rules.
Zero LLM involvement, fail-closed by default.
"""

from typing import Optional

from banking_security.actions import BankingAction, ResourceTarget
from banking_security.context import AuthContext
from banking_security.contracts import PolicyDecision, PolicyReasonCode, PolicyResult
from banking_simulator.models import BeneficiaryStatus, UserStatus
from banking_simulator.simulator import BankingSimulator


class DeterministicPolicyEngine:
    """
    Evaluates authorization policies against caller identity and ground-truth simulator state.
    """

    def evaluate(
        self,
        auth_context: AuthContext,
        action: BankingAction,
        resource_target: ResourceTarget,
        simulator: BankingSimulator,
    ) -> PolicyResult:
        """
        Evaluate an immutable (AuthContext, Action, ResourceTarget, SimulatorState) tuple.
        Returns a deterministic PolicyResult (ALLOW or DENY).
        """
        now_ts = simulator._clock.now_iso()

        # Helper to construct fail-closed denials
        def deny(reason: PolicyReasonCode, message: str) -> PolicyResult:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason_code=reason,
                message=message,
                evaluated_at=now_ts,
                principal_id=auth_context.principal_id,
                action=action,
                resource_id=resource_target.resource_id,
            )

        # Helper to construct allowances
        def allow(message: str = "Authorized") -> PolicyResult:
            return PolicyResult(
                decision=PolicyDecision.ALLOW,
                reason_code=PolicyReasonCode.AUTHORIZED,
                message=message,
                evaluated_at=now_ts,
                principal_id=auth_context.principal_id,
                action=action,
                resource_id=resource_target.resource_id,
            )

        # ----------------------------------------------------------------------
        # 1. Authentication Gate
        # ----------------------------------------------------------------------
        if not auth_context.authenticated or not auth_context.principal_id:
            return deny(
                PolicyReasonCode.UNAUTHENTICATED,
                "Authentication required: valid session token required",
            )

        principal_id = auth_context.principal_id

        # ----------------------------------------------------------------------
        # 2. Principal Existence & Standing Gate
        # ----------------------------------------------------------------------
        user = simulator.get_user(principal_id)
        if not user:
            return deny(
                PolicyReasonCode.UNKNOWN_PRINCIPAL,
                f"Principal '{principal_id}' does not exist in simulator",
            )

        if user.status == UserStatus.SUSPENDED:
            return deny(
                PolicyReasonCode.USER_SUSPENDED,
                f"Principal '{principal_id}' standing is SUSPENDED: all protected operations denied",
            )

        if user.status != UserStatus.ACTIVE:
            return deny(
                PolicyReasonCode.PERMISSION_DENIED,
                f"Principal '{principal_id}' standing is {user.status}: action not permitted",
            )

        # ----------------------------------------------------------------------
        # 3. Action-Specific Ownership & Privilege Evaluation
        # ----------------------------------------------------------------------
        res_id = resource_target.resource_id

        if action in (
            BankingAction.READ_ACCOUNT,
            BankingAction.READ_BALANCE,
            BankingAction.READ_TRANSACTIONS,
        ):
            account = simulator.get_account(res_id)
            if not account:
                return deny(PolicyReasonCode.RESOURCE_NOT_FOUND, f"Account '{res_id}' not found")
            if account.user_id != principal_id:
                return deny(
                    PolicyReasonCode.OWNERSHIP_MISMATCH,
                    f"Principal '{principal_id}' does not own account '{res_id}'",
                )
            return allow(f"Access granted to account '{res_id}'")

        elif action == BankingAction.TRANSFER:
            # Source account ownership check
            source_acc = simulator.get_account(res_id)
            if not source_acc:
                return deny(PolicyReasonCode.RESOURCE_NOT_FOUND, f"Source account '{res_id}' not found")
            if source_acc.user_id != principal_id:
                return deny(
                    PolicyReasonCode.OWNERSHIP_MISMATCH,
                    f"Principal '{principal_id}' does not own source account '{res_id}'",
                )
            # Crucial direct transfer semantic:
            # Destination account is a transaction target, NOT an authorization resource the sender must own.
            return allow(f"Transfer authorized from source account '{res_id}'")

        elif action == BankingAction.TRANSFER_TO_BENEFICIARY:
            # 1. Source account ownership check
            source_acc = simulator.get_account(res_id)
            if not source_acc:
                return deny(PolicyReasonCode.RESOURCE_NOT_FOUND, f"Source account '{res_id}' not found")
            if source_acc.user_id != principal_id:
                return deny(
                    PolicyReasonCode.OWNERSHIP_MISMATCH,
                    f"Principal '{principal_id}' does not own source account '{res_id}'",
                )

            # 2. Beneficiary ownership & verification checks
            ben_id = resource_target.secondary_resource_id
            if not ben_id:
                return deny(PolicyReasonCode.FAIL_CLOSED_ERROR, "Missing required secondary beneficiary ID")

            ben = simulator._beneficiaries.get(ben_id)
            if not ben:
                return deny(PolicyReasonCode.RESOURCE_NOT_FOUND, f"Beneficiary '{ben_id}' not found")
            if ben.owner_user_id != principal_id:
                return deny(
                    PolicyReasonCode.BENEFICIARY_OWNERSHIP_MISMATCH,
                    f"Beneficiary '{ben_id}' does not belong to principal '{principal_id}'",
                )
            if ben.status != BeneficiaryStatus.VERIFIED:
                return deny(
                    PolicyReasonCode.BENEFICIARY_NOT_VERIFIED,
                    f"Beneficiary '{ben_id}' is not VERIFIED (status: {ben.status})",
                )

            return allow(f"Beneficiary transfer authorized from '{res_id}' to '{ben_id}'")

        elif action == BankingAction.READ_BENEFICIARY:
            ben = simulator._beneficiaries.get(res_id)
            if not ben:
                return deny(PolicyReasonCode.RESOURCE_NOT_FOUND, f"Beneficiary '{res_id}' not found")
            if ben.owner_user_id != principal_id:
                return deny(
                    PolicyReasonCode.BENEFICIARY_OWNERSHIP_MISMATCH,
                    f"Beneficiary '{res_id}' does not belong to principal '{principal_id}'",
                )
            return allow(f"Access granted to beneficiary '{res_id}'")

        elif action in (BankingAction.READ_CARD, BankingAction.FREEZE_CARD):
            card = simulator.get_card(res_id)
            if not card:
                return deny(PolicyReasonCode.RESOURCE_NOT_FOUND, f"Card '{res_id}' not found")
            if card.user_id != principal_id:
                return deny(
                    PolicyReasonCode.OWNERSHIP_MISMATCH,
                    f"Principal '{principal_id}' does not own card '{res_id}'",
                )
            return allow(f"Action {action} authorized on card '{res_id}'")

        # Fail-closed default for unrecognized actions
        return deny(PolicyReasonCode.FAIL_CLOSED_ERROR, f"Action '{action}' is unrecognized or unsupported")
