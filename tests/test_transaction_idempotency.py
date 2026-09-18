"""
Tests for Authoritative Safety Idempotency, Scoping, Replay, and Conflict Protection.
"""

from decimal import Decimal
import pytest

from banking_safety.config import TransactionSafetyConfig
from banking_safety.contracts import ExecutionGateResult, SafetyReasonCode
from banking_safety.engine import TransactionSafetyEngine
from banking_safety.gateway import SecureExecutionGateway
from banking_safety.idempotency import AuthoritativeIdempotencyStore
from banking_safety.request import TransactionRequest
from banking_security.actions import BankingAction
from banking_simulator.clock import SimulatedClock
from banking_simulator.contracts import ErrorCode, FailureMode
from banking_simulator.simulator import BankingSimulator


def test_first_execution_and_exact_replay_zero_simulator_invocation():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    gateway = SecureExecutionGateway(simulator=sim, safety_engine=TransactionSafetyEngine(clock=clock))

    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("1000.00"),
        currency="INR",
        idempotency_key="idemp_key_1",
    )

    alice_initial = sim.get_balance("acc_alice_chk")
    bob_initial = sim.get_balance("acc_bob_chk")

    # First call: executes and commits
    res1 = gateway.execute_transaction(session_token="token_alice", request=req)
    assert res1.success is True
    assert res1.cached_replay is False
    assert res1.transaction_id is not None
    assert sim.get_balance("acc_alice_chk") == alice_initial - Decimal("1000.00")
    assert sim.get_balance("acc_bob_chk") == bob_initial + Decimal("1000.00")

    tx_count_after_first = len(sim.get_transactions("acc_alice_chk"))

    # Second call (exact replay): must return cached result without second debit
    res2 = gateway.execute_transaction(session_token="token_alice", request=req)
    assert res2.success is True
    assert res2.cached_replay is True
    assert res2.transaction_id == res1.transaction_id

    # Invariants: Zero state mutation, zero extra simulator transactions
    assert sim.get_balance("acc_alice_chk") == alice_initial - Decimal("1000.00")
    assert sim.get_balance("acc_bob_chk") == bob_initial + Decimal("1000.00")
    assert len(sim.get_transactions("acc_alice_chk")) == tx_count_after_first


def test_idempotency_conflict_on_mismatched_amount():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    gateway = SecureExecutionGateway(simulator=sim, safety_engine=TransactionSafetyEngine(clock=clock))

    req1 = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("1000.00"),
        currency="INR",
        idempotency_key="idemp_conflict_amt",
    )
    res1 = gateway.execute_transaction(session_token="token_alice", request=req1)
    assert res1.success is True

    # Same key with different amount (₹1500)
    req2 = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("1500.00"),
        currency="INR",
        idempotency_key="idemp_conflict_amt",
    )
    res2 = gateway.execute_transaction(session_token="token_alice", request=req2)
    assert res2.success is False
    assert res2.error_code == SafetyReasonCode.IDEMPOTENCY_CONFLICT
    assert "different transaction parameters" in res2.message


def test_idempotency_conflict_on_mismatched_recipient():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    gateway = SecureExecutionGateway(simulator=sim, safety_engine=TransactionSafetyEngine(clock=clock))

    req1 = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("500.00"),
        currency="INR",
        idempotency_key="idemp_conflict_recip",
    )
    res1 = gateway.execute_transaction(session_token="token_alice", request=req1)
    assert res1.success is True

    # Same key with different destination account
    req2 = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_alice_sav",
        amount=Decimal("500.00"),
        currency="INR",
        idempotency_key="idemp_conflict_recip",
    )
    res2 = gateway.execute_transaction(session_token="token_alice", request=req2)
    assert res2.success is False
    assert res2.error_code == SafetyReasonCode.IDEMPOTENCY_CONFLICT


def test_principal_scoping_prevents_cross_user_collision():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    gateway = SecureExecutionGateway(simulator=sim, safety_engine=TransactionSafetyEngine(clock=clock))

    # Alice and Bob both use the same idempotency key "client_tx_001"
    key = "client_tx_001"

    req_alice = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("100.00"),
        currency="INR",
        idempotency_key=key,
    )
    req_bob = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_bob_chk",
        destination_account_id="acc_alice_chk",
        amount=Decimal("200.00"),
        currency="INR",
        idempotency_key=key,
    )

    res_alice = gateway.execute_transaction(session_token="token_alice", request=req_alice)
    assert res_alice.success is True

    # Bob executing with the same key should NOT conflict with Alice
    res_bob = gateway.execute_transaction(session_token="token_bob", request=req_bob)
    assert res_bob.success is True
    assert res_bob.transaction_id != res_alice.transaction_id


def test_insufficient_funds_does_not_commit_key_and_allows_retry():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    gateway = SecureExecutionGateway(simulator=sim, safety_engine=TransactionSafetyEngine(clock=clock))

    # Alice has ₹10,000 checking. Attempt transfer of ₹15,000
    # Use config with per_tx_limit of ₹20,000 so safety passes but simulator rejects
    config = TransactionSafetyConfig(
        per_transaction_limit=Decimal("25000.00"),
        step_up_threshold=Decimal("20000.00"),
    )
    gateway.safety_engine._config = config

    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("15000.00"),
        currency="INR",
        idempotency_key="retry_funds_key",
    )

    # First attempt fails at simulator
    res1 = gateway.execute_transaction(session_token="token_alice", request=req)
    assert res1.success is False
    assert res1.error_code == ErrorCode.INSUFFICIENT_FUNDS

    # Key must NOT be recorded in idempotency store
    cached, status = gateway.safety_engine.idempotency_store.check(
        principal_id="user_001",
        idempotency_key="retry_funds_key",
        fingerprint=req.compute_fingerprint(),
    )
    assert cached is None
    assert status is None

    # Alice receives funds in checking
    sim._accounts["acc_alice_chk"].balance += Decimal("10000.00")

    # Retry with exact same idempotency key now succeeds!
    res2 = gateway.execute_transaction(session_token="token_alice", request=req)
    assert res2.success is True
    assert res2.transaction_id is not None


def test_pre_commit_failure_does_not_commit_key():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    gateway = SecureExecutionGateway(simulator=sim, safety_engine=TransactionSafetyEngine(clock=clock))

    sim.inject_failure(FailureMode.PRE_COMMIT_FAILURE)

    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("500.00"),
        currency="INR",
        idempotency_key="pre_commit_key",
    )

    res1 = gateway.execute_transaction(session_token="token_alice", request=req)
    assert res1.success is False
    assert res1.error_code == ErrorCode.SIMULATED_FAILURE

    # Clear failure injection and retry with same key
    sim.inject_failure(FailureMode.NONE)
    res2 = gateway.execute_transaction(session_token="token_alice", request=req)
    assert res2.success is True
    assert res2.transaction_id is not None
