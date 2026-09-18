"""
Tests for Layer Separation between Security Authorization and Business Policy.
"""

from decimal import Decimal
from unittest.mock import patch
import pytest

from banking_security.actions import BankingAction, ResourceTarget, ResourceType
from banking_security.context import SimulatedSessionManager
from banking_security.contracts import PolicyDecision, PolicyReasonCode
from banking_security.engine import DeterministicPolicyEngine
from banking_security.gateway import SecureBankingGateway
from banking_simulator.contracts import ErrorCode
from banking_simulator.simulator import BankingSimulator


def test_authorization_denial_prevents_simulator_invocation():
    """
    Critical Invariant:
    When authorization denies a request, the underlying BankingSimulator transfer
    method must NEVER be called, and zero state changes can occur.
    """
    sim = BankingSimulator(seed_default_fixtures=True)
    gateway = SecureBankingGateway(simulator=sim)

    # Track initial state
    initial_tx_count = len(sim._transactions)

    # Alice tries to transfer from Bob's account (unauthorized)
    res = gateway.transfer(
        session_token="token_alice",
        source_account_id="acc_bob_chk",
        destination_account_id="acc_alice_chk",
        amount=Decimal("100.00"),
    )

    assert res.success is False
    assert res.error_code == ErrorCode.PERMISSION_DENIED
    assert len(sim._transactions) == initial_tx_count


def test_layer_separation_authorized_with_insufficient_funds():
    """
    Decoupling Invariant:
    Proves authorization and business validation are separate layers.

    Alice attempts to transfer INR 50,000 from her checking account (balance: INR 10,000).
    1. Layer 2 (Policy Engine) evaluates: Alice is authenticated and owns source account.
       Decision: ALLOW (Authorized).
    2. Layer 3 (Banking Simulator) evaluates: Balance is insufficient.
       Result: INSUFFICIENT_FUNDS rejection.
    """
    sim = BankingSimulator(seed_default_fixtures=True)
    sessions = SimulatedSessionManager(sim)
    engine = DeterministicPolicyEngine()
    gateway = SecureBankingGateway(simulator=sim, session_manager=sessions, policy_engine=engine)

    # Step 1: Verify Layer 2 authorization directly
    auth_alice = sessions.authenticate("token_alice")
    target = ResourceTarget(
        resource_type=ResourceType.ACCOUNT,
        resource_id="acc_alice_chk",
        secondary_resource_id="acc_bob_chk",
    )
    policy_result = engine.evaluate(auth_alice, BankingAction.TRANSFER, target, sim)
    assert policy_result.decision == PolicyDecision.ALLOW
    assert policy_result.reason_code == PolicyReasonCode.AUTHORIZED

    # Step 2: Execute through Gateway -> Simulator enforces business balance check
    alice_before = sim.get_balance("acc_alice_chk")
    res = gateway.transfer(
        session_token="token_alice",
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("50000.00"),
    )

    assert res.success is False
    assert res.error_code == ErrorCode.INSUFFICIENT_FUNDS
    assert "Insufficient balance" in res.message
    # State remains untouched
    assert sim.get_balance("acc_alice_chk") == alice_before


def test_layer_separation_authorized_with_frozen_destination():
    """
    Alice transfers to Bob's frozen account ('acc_bob_frz').
    1. Layer 2 (Authorization) passes: Alice owns source account.
    2. Layer 3 (Simulator) rejects: Destination account is frozen.
    """
    sim = BankingSimulator(seed_default_fixtures=True)
    gateway = SecureBankingGateway(simulator=sim)

    alice_before = sim.get_balance("acc_alice_chk")
    bob_frz_before = sim.get_balance("acc_bob_frz")

    res = gateway.transfer(
        session_token="token_alice",
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_frz",
        amount=Decimal("500.00"),
    )

    assert res.success is False
    assert res.error_code == ErrorCode.ACCOUNT_FROZEN
    assert sim.get_balance("acc_alice_chk") == alice_before
    assert sim.get_balance("acc_bob_frz") == bob_frz_before
