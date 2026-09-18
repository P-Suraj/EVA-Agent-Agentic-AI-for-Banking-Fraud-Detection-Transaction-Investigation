"""
Tests for Deterministic Policy Engine (src/banking_security/engine.py).

Verifies the 15 required security test cases, ownership rules,
least privilege, and fail-closed behavior.
"""

from banking_security.actions import BankingAction, ResourceTarget, ResourceType
from banking_security.context import AuthContext, SimulatedSessionManager
from banking_security.contracts import PolicyDecision, PolicyReasonCode
from banking_security.engine import DeterministicPolicyEngine
from banking_simulator.simulator import BankingSimulator


def test_own_account_read_allowed():
    sim = BankingSimulator(seed_default_fixtures=True)
    engine = DeterministicPolicyEngine()
    ctx = AuthContext(principal_id="user_001", authenticated=True, session_id="tok", roles=["CUSTOMER"])
    target = ResourceTarget(resource_type=ResourceType.ACCOUNT, resource_id="acc_alice_chk")

    res = engine.evaluate(ctx, BankingAction.READ_ACCOUNT, target, sim)
    assert res.decision == PolicyDecision.ALLOW
    assert res.reason_code == PolicyReasonCode.AUTHORIZED


def test_cross_user_account_read_denied():
    sim = BankingSimulator(seed_default_fixtures=True)
    engine = DeterministicPolicyEngine()
    ctx = AuthContext(principal_id="user_001", authenticated=True, session_id="tok", roles=["CUSTOMER"])
    target = ResourceTarget(resource_type=ResourceType.ACCOUNT, resource_id="acc_bob_chk")

    res = engine.evaluate(ctx, BankingAction.READ_ACCOUNT, target, sim)
    assert res.decision == PolicyDecision.DENY
    assert res.reason_code == PolicyReasonCode.OWNERSHIP_MISMATCH


def test_cross_user_balance_read_denied():
    sim = BankingSimulator(seed_default_fixtures=True)
    engine = DeterministicPolicyEngine()
    ctx = AuthContext(principal_id="user_001", authenticated=True, session_id="tok", roles=["CUSTOMER"])
    target = ResourceTarget(resource_type=ResourceType.ACCOUNT, resource_id="acc_bob_chk")

    res = engine.evaluate(ctx, BankingAction.READ_BALANCE, target, sim)
    assert res.decision == PolicyDecision.DENY
    assert res.reason_code == PolicyReasonCode.OWNERSHIP_MISMATCH


def test_cross_user_transactions_read_denied():
    sim = BankingSimulator(seed_default_fixtures=True)
    engine = DeterministicPolicyEngine()
    ctx = AuthContext(principal_id="user_001", authenticated=True, session_id="tok", roles=["CUSTOMER"])
    target = ResourceTarget(resource_type=ResourceType.ACCOUNT, resource_id="acc_bob_chk")

    res = engine.evaluate(ctx, BankingAction.READ_TRANSACTIONS, target, sim)
    assert res.decision == PolicyDecision.DENY
    assert res.reason_code == PolicyReasonCode.OWNERSHIP_MISMATCH


def test_direct_transfer_own_source_to_other_destination_allowed():
    """
    Direct Transfer Semantics:
    Alice transfers to Bob. Authorization requires Alice to own the source account.
    Destination account is a transaction target, not an authorization resource that Alice must own.
    """
    sim = BankingSimulator(seed_default_fixtures=True)
    engine = DeterministicPolicyEngine()
    ctx = AuthContext(principal_id="user_001", authenticated=True, session_id="tok", roles=["CUSTOMER"])
    target = ResourceTarget(
        resource_type=ResourceType.ACCOUNT,
        resource_id="acc_alice_chk",
        secondary_resource_id="acc_bob_chk",
    )

    res = engine.evaluate(ctx, BankingAction.TRANSFER, target, sim)
    assert res.decision == PolicyDecision.ALLOW
    assert res.reason_code == PolicyReasonCode.AUTHORIZED


def test_direct_transfer_cross_user_source_denied():
    """Alice attempts to transfer from Bob's source account -> DENY."""
    sim = BankingSimulator(seed_default_fixtures=True)
    engine = DeterministicPolicyEngine()
    ctx = AuthContext(principal_id="user_001", authenticated=True, session_id="tok", roles=["CUSTOMER"])
    target = ResourceTarget(
        resource_type=ResourceType.ACCOUNT,
        resource_id="acc_bob_chk",
        secondary_resource_id="acc_alice_chk",
    )

    res = engine.evaluate(ctx, BankingAction.TRANSFER, target, sim)
    assert res.decision == PolicyDecision.DENY
    assert res.reason_code == PolicyReasonCode.OWNERSHIP_MISMATCH


def test_beneficiary_transfer_own_verified_allowed():
    """Alice transfers from Alice account to Alice's verified beneficiary Bob -> ALLOW."""
    sim = BankingSimulator(seed_default_fixtures=True)
    engine = DeterministicPolicyEngine()
    ctx = AuthContext(principal_id="user_001", authenticated=True, session_id="tok", roles=["CUSTOMER"])
    target = ResourceTarget(
        resource_type=ResourceType.ACCOUNT,
        resource_id="acc_alice_chk",
        secondary_resource_id="ben_bob_01",
    )

    res = engine.evaluate(ctx, BankingAction.TRANSFER_TO_BENEFICIARY, target, sim)
    assert res.decision == PolicyDecision.ALLOW
    assert res.reason_code == PolicyReasonCode.AUTHORIZED


def test_beneficiary_transfer_cross_user_beneficiary_denied():
    """Alice attempts to transfer to a beneficiary registered by Bob -> DENY."""
    sim = BankingSimulator(seed_default_fixtures=True)
    # Register a beneficiary owned by Bob
    from banking_simulator.models import Beneficiary, BeneficiaryStatus
    sim._beneficiaries["ben_owned_by_bob"] = Beneficiary(
        beneficiary_id="ben_owned_by_bob",
        owner_user_id="user_002",
        name="Bob's Friend",
        account_reference="acc_alice_chk",
        status=BeneficiaryStatus.VERIFIED,
    )

    engine = DeterministicPolicyEngine()
    ctx = AuthContext(principal_id="user_001", authenticated=True, session_id="tok", roles=["CUSTOMER"])
    target = ResourceTarget(
        resource_type=ResourceType.ACCOUNT,
        resource_id="acc_alice_chk",
        secondary_resource_id="ben_owned_by_bob",
    )

    res = engine.evaluate(ctx, BankingAction.TRANSFER_TO_BENEFICIARY, target, sim)
    assert res.decision == PolicyDecision.DENY
    assert res.reason_code == PolicyReasonCode.BENEFICIARY_OWNERSHIP_MISMATCH


def test_beneficiary_transfer_pending_beneficiary_denied():
    """Alice attempts to transfer to her own unverified/pending beneficiary Charlie -> DENY."""
    sim = BankingSimulator(seed_default_fixtures=True)
    engine = DeterministicPolicyEngine()
    ctx = AuthContext(principal_id="user_001", authenticated=True, session_id="tok", roles=["CUSTOMER"])
    target = ResourceTarget(
        resource_type=ResourceType.ACCOUNT,
        resource_id="acc_alice_chk",
        secondary_resource_id="ben_charlie_02",  # Status is PENDING in default fixtures
    )

    res = engine.evaluate(ctx, BankingAction.TRANSFER_TO_BENEFICIARY, target, sim)
    assert res.decision == PolicyDecision.DENY
    assert res.reason_code == PolicyReasonCode.BENEFICIARY_NOT_VERIFIED


def test_card_freeze_own_card_allowed():
    sim = BankingSimulator(seed_default_fixtures=True)
    engine = DeterministicPolicyEngine()
    ctx = AuthContext(principal_id="user_001", authenticated=True, session_id="tok", roles=["CUSTOMER"])
    target = ResourceTarget(resource_type=ResourceType.CARD, resource_id="card_alice_01")

    res = engine.evaluate(ctx, BankingAction.FREEZE_CARD, target, sim)
    assert res.decision == PolicyDecision.ALLOW
    assert res.reason_code == PolicyReasonCode.AUTHORIZED


def test_card_freeze_cross_user_card_denied():
    sim = BankingSimulator(seed_default_fixtures=True)
    engine = DeterministicPolicyEngine()
    ctx = AuthContext(principal_id="user_001", authenticated=True, session_id="tok", roles=["CUSTOMER"])
    target = ResourceTarget(resource_type=ResourceType.CARD, resource_id="card_bob_01")

    res = engine.evaluate(ctx, BankingAction.FREEZE_CARD, target, sim)
    assert res.decision == PolicyDecision.DENY
    assert res.reason_code == PolicyReasonCode.OWNERSHIP_MISMATCH


def test_suspended_user_denied():
    sim = BankingSimulator(seed_default_fixtures=True)
    mgr = SimulatedSessionManager(sim)
    engine = DeterministicPolicyEngine()

    ctx = mgr.authenticate("token_suspended")
    target = ResourceTarget(resource_type=ResourceType.ACCOUNT, resource_id="acc_alice_chk")

    res = engine.evaluate(ctx, BankingAction.READ_ACCOUNT, target, sim)
    assert res.decision == PolicyDecision.DENY
    assert res.reason_code == PolicyReasonCode.USER_SUSPENDED


def test_unknown_principal_denied():
    sim = BankingSimulator(seed_default_fixtures=True)
    engine = DeterministicPolicyEngine()
    ctx = AuthContext(principal_id="user_ghost", authenticated=True, session_id="tok", roles=["CUSTOMER"])
    target = ResourceTarget(resource_type=ResourceType.ACCOUNT, resource_id="acc_alice_chk")

    res = engine.evaluate(ctx, BankingAction.READ_ACCOUNT, target, sim)
    assert res.decision == PolicyDecision.DENY
    assert res.reason_code == PolicyReasonCode.UNKNOWN_PRINCIPAL


def test_unknown_resource_denied():
    sim = BankingSimulator(seed_default_fixtures=True)
    engine = DeterministicPolicyEngine()
    ctx = AuthContext(principal_id="user_001", authenticated=True, session_id="tok", roles=["CUSTOMER"])
    target = ResourceTarget(resource_type=ResourceType.ACCOUNT, resource_id="nonexistent_acc")

    res = engine.evaluate(ctx, BankingAction.READ_ACCOUNT, target, sim)
    assert res.decision == PolicyDecision.DENY
    assert res.reason_code == PolicyReasonCode.RESOURCE_NOT_FOUND


def test_unauthenticated_caller_denied_fail_closed():
    sim = BankingSimulator(seed_default_fixtures=True)
    engine = DeterministicPolicyEngine()
    ctx = AuthContext(principal_id=None, authenticated=False, session_id=None, roles=[])
    target = ResourceTarget(resource_type=ResourceType.ACCOUNT, resource_id="acc_alice_chk")

    res = engine.evaluate(ctx, BankingAction.READ_ACCOUNT, target, sim)
    assert res.decision == PolicyDecision.DENY
    assert res.reason_code == PolicyReasonCode.UNAUTHENTICATED
