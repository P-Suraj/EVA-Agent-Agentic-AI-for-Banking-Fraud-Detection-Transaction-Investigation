"""
Tests for 4-Layer Execution Gate Composition and Zero-Invocation Invariants.
"""

from decimal import Decimal
from unittest.mock import patch
import pytest

from banking_safety.config import TransactionSafetyConfig
from banking_safety.contracts import SafetyReasonCode
from banking_safety.engine import TransactionSafetyEngine
from banking_safety.gateway import SecureExecutionGateway
from banking_safety.request import TransactionRequest
from banking_security.actions import BankingAction
from banking_simulator.clock import SimulatedClock
from banking_simulator.contracts import ErrorCode, FailureMode
from banking_simulator.simulator import BankingSimulator


def test_full_pipeline_success_end_to_end():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    gateway = SecureExecutionGateway(simulator=sim, safety_engine=TransactionSafetyEngine(clock=clock))

    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("1500.00"),
        currency="INR",
        idempotency_key="pipe_success_1",
    )

    alice_init = sim.get_balance("acc_alice_chk")
    bob_init = sim.get_balance("acc_bob_chk")

    res = gateway.execute_transaction(session_token="token_alice", request=req)
    assert res.success is True
    assert res.transaction_id == "tx_0001"
    assert sim.get_balance("acc_alice_chk") == alice_init - Decimal("1500.00")
    assert sim.get_balance("acc_bob_chk") == bob_init + Decimal("1500.00")


def test_beneficiary_transfer_end_to_end():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    gateway = SecureExecutionGateway(simulator=sim, safety_engine=TransactionSafetyEngine(clock=clock))

    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER_TO_BENEFICIARY,
        source_account_id="acc_alice_chk",
        beneficiary_id="ben_bob_01",
        amount=Decimal("500.00"),
        currency="INR",
        idempotency_key="pipe_ben_1",
    )

    res = gateway.execute_transaction(session_token="token_alice", request=req)
    assert res.success is True
    assert res.transaction_id is not None
    assert res.data.beneficiary_id == "ben_bob_01"


def test_simulator_mutation_count_zero_on_all_pre_execution_denials():
    """
    Core Security Invariant:
    Simulator mutation methods (_execute_transfer, transfer, transfer_to_beneficiary)
    must have an invocation count of strictly ZERO for all pre-execution denials.
    """
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    config = TransactionSafetyConfig(
        per_transaction_limit=Decimal("5000.00"),
        daily_transfer_limit=Decimal("10000.00"),
        step_up_threshold=Decimal("8000.00"),
        velocity_count_limit=2,
    )
    gateway = SecureExecutionGateway(
        simulator=sim,
        safety_engine=TransactionSafetyEngine(clock=clock, config=config),
    )

    with patch.object(sim, "_execute_transfer", wraps=sim._execute_transfer) as mock_sim:
        # Case 1: Layer 1 Unauthenticated
        req1 = TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",
            amount=Decimal("100.00"),
            currency="INR",
            idempotency_key="deny_1",
        )
        res1 = gateway.execute_transaction(session_token=None, request=req1)
        assert res1.success is False
        assert mock_sim.call_count == 0

        # Case 2: Layer 2 Unauthorized (Alice tries to debit Bob's account)
        req2 = TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_bob_chk",
            destination_account_id="acc_alice_chk",
            amount=Decimal("100.00"),
            currency="INR",
            idempotency_key="deny_2",
        )
        res2 = gateway.execute_transaction(session_token="token_alice", request=req2)
        assert res2.success is False
        assert res2.error_code == ErrorCode.PERMISSION_DENIED
        assert mock_sim.call_count == 0

        # Case 3: Layer 2 Suspended User
        req3 = TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",
            amount=Decimal("100.00"),
            currency="INR",
            idempotency_key="deny_3",
        )
        res3 = gateway.execute_transaction(session_token="token_suspended", request=req3)
        assert res3.success is False
        assert mock_sim.call_count == 0

        # Case 4: Layer 3 Per-Transaction Limit Exceeded (> ₹5,000)
        req4 = TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",
            amount=Decimal("6000.00"),
            currency="INR",
            idempotency_key="deny_4",
        )
        res4 = gateway.execute_transaction(session_token="token_alice", request=req4)
        assert res4.success is False
        assert res4.error_code == SafetyReasonCode.PER_TRANSACTION_LIMIT_EXCEEDED
        assert mock_sim.call_count == 0

        # Case 5: Layer 3 Unsupported Currency (USD)
        req5 = TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",
            amount=Decimal("100.00"),
            currency="USD",
            idempotency_key="deny_5",
        )
        res5 = gateway.execute_transaction(session_token="token_alice", request=req5)
        assert res5.success is False
        assert res5.error_code == SafetyReasonCode.CURRENCY_UNSUPPORTED
        assert mock_sim.call_count == 0

        # Case 6: Layer 3 Missing Step-Up Approval (amount ₹4,500 with threshold lowered to ₹4,000)
        gateway.safety_engine._config = TransactionSafetyConfig(
            per_transaction_limit=Decimal("50000.00"),
            step_up_threshold=Decimal("4000.00"),
        )
        req6 = TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",
            amount=Decimal("4500.00"),
            currency="INR",
            idempotency_key="deny_6",
        )
        res6 = gateway.execute_transaction(session_token="token_alice", request=req6, approval=None)
        assert res6.success is False
        assert res6.error_code == SafetyReasonCode.STEP_UP_REQUIRED
        assert mock_sim.call_count == 0

        # Overall Invariant across all 6 denial scenarios:
        assert mock_sim.call_count == 0


def test_insufficient_funds_simulator_failure_isolation():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    gateway = SecureExecutionGateway(simulator=sim, safety_engine=TransactionSafetyEngine(clock=clock))

    alice_before = sim.get_balance("acc_alice_chk")
    bob_before = sim.get_balance("acc_bob_chk")

    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("20000.00"),  # Alice has ₹10,000
        currency="INR",
        idempotency_key="k_funds_iso",
    )
    # Give high limit so it reaches simulator
    gateway.safety_engine._config = TransactionSafetyConfig(
        per_transaction_limit=Decimal("50000.00"),
        step_up_threshold=Decimal("30000.00"),
    )

    res = gateway.execute_transaction(session_token="token_alice", request=req)
    assert res.success is False
    assert res.error_code == ErrorCode.INSUFFICIENT_FUNDS

    # Balances must be 100% unchanged
    assert sim.get_balance("acc_alice_chk") == alice_before
    assert sim.get_balance("acc_bob_chk") == bob_before
    assert len(sim.get_transactions("acc_alice_chk")) == 0
