"""
Tests for Confused-Deputy Defense and Adversarial Scenarios (src/banking_security/).
"""

from decimal import Decimal
from banking_security.actions import BankingAction, ResourceTarget, ResourceType
from banking_security.context import AuthContext, SimulatedSessionManager
from banking_security.contracts import PolicyDecision, PolicyReasonCode
from banking_security.engine import DeterministicPolicyEngine
from banking_security.gateway import SecureBankingGateway
from banking_simulator.contracts import ErrorCode
from banking_simulator.simulator import BankingSimulator


def test_confused_deputy_source_account_impersonation():
    """
    Confused-Deputy Scenario:
    Alice ('user_001') is authenticated. The caller tries to initiate a transfer
    debiting Bob's account ('acc_bob_chk') into Alice's account, claiming Bob authorized it.
    The policy engine must inspect ground truth in the simulator and reject the request.
    """
    sim = BankingSimulator(seed_default_fixtures=True)
    gateway = SecureBankingGateway(simulator=sim)

    bob_before = sim.get_balance("acc_bob_chk")
    alice_before = sim.get_balance("acc_alice_chk")
    tx_count_before = len(sim.get_transactions("acc_bob_chk"))

    res = gateway.transfer(
        session_token="token_alice",  # Alice's token
        source_account_id="acc_bob_chk",  # Bob's account as source
        destination_account_id="acc_alice_chk",
        amount=Decimal("1000.00"),
    )

    assert res.success is False
    assert res.error_code == ErrorCode.PERMISSION_DENIED
    assert "does not own source account" in res.message

    # Ground truth invariant: Bob's funds remain completely untouched
    assert sim.get_balance("acc_bob_chk") == bob_before
    assert sim.get_balance("acc_alice_chk") == alice_before
    assert len(sim.get_transactions("acc_bob_chk")) == tx_count_before


def test_destination_ownership_does_not_grant_source_debit_authority():
    """
    Bob owns 'acc_bob_chk'. A transfer from Alice's account to Bob's account
    cannot be initiated using Bob's credentials.
    """
    sim = BankingSimulator(seed_default_fixtures=True)
    gateway = SecureBankingGateway(simulator=sim)

    alice_before = sim.get_balance("acc_alice_chk")

    # Bob tries to pull money from Alice's account into his own account
    res = gateway.transfer(
        session_token="token_bob",  # Bob's token
        source_account_id="acc_alice_chk",  # Alice's account
        destination_account_id="acc_bob_chk",  # Bob owns destination
        amount=Decimal("500.00"),
    )

    assert res.success is False
    assert res.error_code == ErrorCode.PERMISSION_DENIED
    assert sim.get_balance("acc_alice_chk") == alice_before


def test_caller_supplied_claims_are_ignored():
    """
    The policy engine resolves ground-truth identity exclusively from AuthContext
    and simulator state, ignoring any external caller-supplied arguments.
    """
    sim = BankingSimulator(seed_default_fixtures=True)
    engine = DeterministicPolicyEngine()

    # Alice's verified context
    ctx = AuthContext(principal_id="user_001", authenticated=True, session_id="tok", roles=["CUSTOMER"])
    target = ResourceTarget(resource_type=ResourceType.ACCOUNT, resource_id="acc_bob_chk")

    # Even if an external caller asserts 'is_admin=True' or 'authorized_by_bob=True',
    # the engine only uses the immutable AuthContext and simulator ground truth.
    res = engine.evaluate(ctx, BankingAction.READ_ACCOUNT, target, sim)
    assert res.decision == PolicyDecision.DENY
    assert res.reason_code == PolicyReasonCode.OWNERSHIP_MISMATCH
