"""
Tests for TransactionSafetyEngine Precedence, Orchestration, and Short-Circuiting.
"""

from decimal import Decimal
import pytest

from banking_safety.config import TransactionSafetyConfig
from banking_safety.contracts import (
    ExecutionGateResult,
    GateStage,
    SafetyDecision,
    SafetyReasonCode,
)
from banking_safety.engine import TransactionSafetyEngine
from banking_safety.request import TransactionRequest
from banking_security.actions import BankingAction
from banking_security.context import AuthContext
from banking_simulator.clock import SimulatedClock
from banking_simulator.simulator import BankingSimulator


def test_missing_idempotency_key_fails_closed_first():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    engine = TransactionSafetyEngine(clock=clock)
    auth = AuthContext(principal_id="user_001", authenticated=True, session_id="s1")

    # Manually bypass Pydantic model validation to test engine fail-closed guard
    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("100.00"),
        currency="INR",
        idempotency_key="dummy",
    )
    object.__setattr__(req, "idempotency_key", "")

    res = engine.evaluate(req, auth, sim)
    assert res.decision == SafetyDecision.DENY
    assert res.reason_code == SafetyReasonCode.MISSING_IDEMPOTENCY_KEY


def test_idempotency_replay_short_circuits_limits():
    """
    Critical Invariant:
    If a transaction was previously committed and now reaches the safety engine as a replay,
    it must return IDEMPOTENCY_REPLAY without re-evaluating limits (which may now be exhausted).
    """
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    config = TransactionSafetyConfig(
        per_transaction_limit=Decimal("5000.00"),
        daily_transfer_limit=Decimal("5000.00"),
    )
    engine = TransactionSafetyEngine(clock=clock, config=config)
    auth = AuthContext(principal_id="user_001", authenticated=True, session_id="s1")

    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("5000.00"),
        currency="INR",
        idempotency_key="k_exhaust_replay",
    )

    # Pre-commit an outcome into idempotency store (simulating previous execution)
    fake_result = ExecutionGateResult(
        success=True,
        error_code="SUCCESS",
        message="Cached transfer",
        transaction_id="tx_0001",
        gate_stage=GateStage.SIMULATOR_EXECUTION,
    )
    engine.idempotency_store.commit(
        principal_id="user_001",
        idempotency_key="k_exhaust_replay",
        fingerprint=req.compute_fingerprint(),
        result=fake_result,
    )

    # Incur an actual simulator transaction to exhaust daily limit
    sim.transfer("acc_alice_chk", "acc_bob_chk", Decimal("5000.00"))

    # When the replay is evaluated, it must short-circuit and return IDEMPOTENCY_REPLAY
    # rather than failing with DAILY_LIMIT_EXCEEDED!
    res = engine.evaluate(req, auth, sim)
    assert res.decision == SafetyDecision.ALLOW
    assert res.reason_code == SafetyReasonCode.IDEMPOTENCY_REPLAY


def test_currency_check_precedes_limits():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    config = TransactionSafetyConfig(
        per_transaction_limit=Decimal("100.00"),
        currency="INR",
    )
    engine = TransactionSafetyEngine(clock=clock, config=config)
    auth = AuthContext(principal_id="user_001", authenticated=True, session_id="s1")

    # Amount ₹500 exceeds per_transaction_limit ₹100, BUT currency is USD!
    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("500.00"),
        currency="USD",
        idempotency_key="k_cur_order",
    )
    res = engine.evaluate(req, auth, sim)
    assert res.decision == SafetyDecision.DENY
    assert res.reason_code == SafetyReasonCode.CURRENCY_UNSUPPORTED


def test_limits_precede_step_up_check():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    config = TransactionSafetyConfig(
        per_transaction_limit=Decimal("5000.00"),
        step_up_threshold=Decimal("10000.00"),
    )
    engine = TransactionSafetyEngine(clock=clock, config=config)
    auth = AuthContext(principal_id="user_001", authenticated=True, session_id="s1")

    # Transfer of ₹15,000 exceeds per-tx limit (₹5,000) AND exceeds step-up threshold (₹10,000)
    # Per-transaction limit must fail first!
    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("15000.00"),
        currency="INR",
        idempotency_key="k_limit_before_step",
    )
    res = engine.evaluate(req, auth, sim, approval=None)
    assert res.decision == SafetyDecision.DENY
    assert res.reason_code == SafetyReasonCode.PER_TRANSACTION_LIMIT_EXCEEDED
