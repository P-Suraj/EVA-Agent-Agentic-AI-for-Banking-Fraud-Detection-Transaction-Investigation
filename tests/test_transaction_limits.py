"""
Tests for Transaction Limits, Cumulative Daily Limits, Velocity, and Currency Matching.
"""

from decimal import Decimal
import pytest

from banking_safety.config import TransactionSafetyConfig
from banking_safety.contracts import SafetyDecision, SafetyReasonCode
from banking_safety.limits import TransactionLimitEvaluator
from banking_safety.request import TransactionRequest
from banking_security.actions import BankingAction
from banking_simulator.clock import SimulatedClock
from banking_simulator.contracts import FailureMode
from banking_simulator.simulator import BankingSimulator


def test_unsupported_currency_fails_closed():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    evaluator = TransactionLimitEvaluator(clock=clock)
    config = TransactionSafetyConfig(currency="INR")

    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("100.00"),
        currency="USD",
        idempotency_key="k_usd",
    )

    res = evaluator.evaluate_limits(req, sim, config)
    assert res.decision == SafetyDecision.DENY
    assert res.reason_code == SafetyReasonCode.CURRENCY_UNSUPPORTED
    assert "USD" in res.message


def test_per_transaction_limits():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    evaluator = TransactionLimitEvaluator(clock=clock)
    config = TransactionSafetyConfig(per_transaction_limit=Decimal("5000.00"), currency="INR")

    # Below limit
    req_below = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("4999.99"),
        currency="INR",
        idempotency_key="k_below",
    )
    res_below = evaluator.evaluate_limits(req_below, sim, config)
    assert res_below.decision == SafetyDecision.ALLOW

    # Exactly at limit
    req_at = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("5000.00"),
        currency="INR",
        idempotency_key="k_at",
    )
    res_at = evaluator.evaluate_limits(req_at, sim, config)
    assert res_at.decision == SafetyDecision.ALLOW

    # Above limit
    req_above = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("5000.01"),
        currency="INR",
        idempotency_key="k_above",
    )
    res_above = evaluator.evaluate_limits(req_above, sim, config)
    assert res_above.decision == SafetyDecision.DENY
    assert res_above.reason_code == SafetyReasonCode.PER_TRANSACTION_LIMIT_EXCEEDED


def test_daily_cumulative_limit():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    evaluator = TransactionLimitEvaluator(clock=clock)
    config = TransactionSafetyConfig(
        per_transaction_limit=Decimal("20000.00"),
        daily_transfer_limit=Decimal("10000.00"),
        currency="INR",
    )

    # First transfer of ₹6,000 executed in simulator
    sim.transfer("acc_alice_chk", "acc_bob_chk", Decimal("6000.00"), idempotency_key="sim_tx_1")

    # Second transfer of ₹4,000 brings total to exact limit ₹10,000 -> ALLOW
    req_exact = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("4000.00"),
        currency="INR",
        idempotency_key="k_exact",
    )
    res_exact = evaluator.evaluate_limits(req_exact, sim, config)
    assert res_exact.decision == SafetyDecision.ALLOW

    # Attempt to transfer ₹4,000.01 exceeds limit (6000 + 4000.01 = 10000.01) -> DENY
    req_over = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("4000.01"),
        currency="INR",
        idempotency_key="k_over",
    )
    res_over = evaluator.evaluate_limits(req_over, sim, config)
    assert res_over.decision == SafetyDecision.DENY
    assert res_over.reason_code == SafetyReasonCode.DAILY_LIMIT_EXCEEDED


def test_failed_transfers_do_not_count_toward_daily_limit():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    evaluator = TransactionLimitEvaluator(clock=clock)
    config = TransactionSafetyConfig(
        per_transaction_limit=Decimal("20000.00"),
        daily_transfer_limit=Decimal("5000.00"),
        currency="INR",
    )

    # Incur an insufficient funds rejection in simulator
    sim.transfer("acc_alice_chk", "acc_bob_chk", Decimal("99999.00"))

    # Incur a pre-commit failure in simulator
    sim.inject_failure(FailureMode.PRE_COMMIT_FAILURE)
    sim.transfer("acc_alice_chk", "acc_bob_chk", Decimal("3000.00"))
    sim.inject_failure(FailureMode.NONE)

    # Both failed; neither debited Alice's balance or created a POSTED transaction.
    # Alice can still transfer up to the full ₹5,000 daily limit!
    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("5000.00"),
        currency="INR",
        idempotency_key="k_clean",
    )
    res = evaluator.evaluate_limits(req, sim, config)
    assert res.decision == SafetyDecision.ALLOW


def test_different_accounts_have_independent_daily_limits():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    evaluator = TransactionLimitEvaluator(clock=clock)
    config = TransactionSafetyConfig(
        daily_transfer_limit=Decimal("5000.00"),
        per_transaction_limit=Decimal("10000.00"),
        currency="INR",
    )

    # Alice exhausts her checking daily limit
    sim.transfer("acc_alice_chk", "acc_bob_chk", Decimal("5000.00"), idempotency_key="sim_a")

    # Alice's savings account (acc_alice_sav) is unaffected
    req_sav = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("3000.00"),
        currency="INR",
        idempotency_key="k_sav",
    )
    res_sav = evaluator.evaluate_limits(req_sav, sim, config)
    assert res_sav.decision == SafetyDecision.ALLOW

    # Bob's account (acc_bob_chk) is also unaffected
    req_bob = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_bob_chk",
        destination_account_id="acc_alice_chk",
        amount=Decimal("2000.00"),
        currency="INR",
        idempotency_key="k_bob",
    )
    res_bob = evaluator.evaluate_limits(req_bob, sim, config)
    assert res_bob.decision == SafetyDecision.ALLOW


def test_velocity_limit_and_rolling_window():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    evaluator = TransactionLimitEvaluator(clock=clock)
    config = TransactionSafetyConfig(
        velocity_window_seconds=3600,  # 1 hour
        velocity_count_limit=3,        # max 3 transfers per hour
        per_transaction_limit=Decimal("50000.00"),
        daily_transfer_limit=Decimal("100000.00"),
        currency="INR",
    )

    # Execute 3 transactions in simulator
    for i in range(1, 4):
        sim.transfer("acc_alice_chk", "acc_bob_chk", Decimal("100.00"), idempotency_key=f"sim_vel_{i}")

    # 4th transaction within the hour is DENIED by velocity
    req4 = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("100.00"),
        currency="INR",
        idempotency_key="k_vel_4",
    )
    res4 = evaluator.evaluate_limits(req4, sim, config)
    assert res4.decision == SafetyDecision.DENY
    assert res4.reason_code == SafetyReasonCode.VELOCITY_LIMIT_EXCEEDED

    # Advance clock by 3,601 seconds (past the 1-hour window)
    clock.tick(3601)

    # The 3 prior transactions are now outside the rolling window -> ALLOW
    res4_after = evaluator.evaluate_limits(req4, sim, config)
    assert res4_after.decision == SafetyDecision.ALLOW
