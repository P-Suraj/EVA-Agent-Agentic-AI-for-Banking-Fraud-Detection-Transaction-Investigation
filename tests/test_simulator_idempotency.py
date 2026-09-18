"""
Tests for Simulator Idempotency (src/banking_simulator/simulator.py).
"""

from decimal import Decimal
from banking_simulator.contracts import ErrorCode
from banking_simulator.simulator import BankingSimulator


def test_idempotent_duplicate_request_returns_cached_result_without_second_debit():
    sim = BankingSimulator(seed_default_fixtures=True)

    alice_before = sim.get_balance("acc_alice_chk")
    bob_before = sim.get_balance("acc_bob_chk")

    key = "unique_tx_key_123"

    # First call
    res1 = sim.transfer("acc_alice_chk", "acc_bob_chk", Decimal("1000.00"), idempotency_key=key)
    assert res1.success is True
    assert res1.data is not None

    alice_after_first = sim.get_balance("acc_alice_chk")
    bob_after_first = sim.get_balance("acc_bob_chk")
    assert alice_after_first == alice_before - Decimal("1000.00")
    assert bob_after_first == bob_before + Decimal("1000.00")

    # Second call with identical key and parameters (e.g. amount string representation)
    res2 = sim.transfer("acc_alice_chk", "acc_bob_chk", "1000.00", idempotency_key=key)
    assert res2.success is True
    assert res2.transaction_id == res1.transaction_id

    # Balances must NOT be deducted a second time
    assert sim.get_balance("acc_alice_chk") == alice_after_first
    assert sim.get_balance("acc_bob_chk") == bob_after_first
    assert len(sim.get_transactions("acc_alice_chk")) == 1


def test_idempotency_conflict_on_mismatched_payload():
    sim = BankingSimulator(seed_default_fixtures=True)

    key = "reused_key_456"

    # First call: ₹500
    res1 = sim.transfer("acc_alice_chk", "acc_bob_chk", Decimal("500.00"), idempotency_key=key)
    assert res1.success is True

    # Reused key with different amount (₹1000)
    res2 = sim.transfer("acc_alice_chk", "acc_bob_chk", Decimal("1000.00"), idempotency_key=key)
    assert res2.success is False
    assert res2.error_code == ErrorCode.IDEMPOTENCY_CONFLICT


def test_clock_determinism_across_identical_runs():
    """Verify that two simulators initialized identically produce bit-for-bit identical tx IDs and timestamps."""
    sim1 = BankingSimulator(seed_default_fixtures=True)
    sim2 = BankingSimulator(seed_default_fixtures=True)

    res1 = sim1.transfer("acc_alice_chk", "acc_bob_chk", Decimal("100.00"))
    res2 = sim2.transfer("acc_alice_chk", "acc_bob_chk", Decimal("100.00"))

    assert res1.data is not None and res2.data is not None
    assert res1.data.transaction_id == res2.data.transaction_id == "tx_0001"
    assert res1.data.timestamp == res2.data.timestamp == "2026-01-01T12:00:00+00:00"
