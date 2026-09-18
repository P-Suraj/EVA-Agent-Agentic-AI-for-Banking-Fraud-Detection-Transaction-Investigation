"""
Tests for Controlled Failure Injection (src/banking_simulator/simulator.py).
"""

from decimal import Decimal
from banking_simulator.contracts import ErrorCode, FailureMode
from banking_simulator.simulator import BankingSimulator


def test_pre_commit_failure_injection_preserves_state():
    """
    Verify that an injected PRE_COMMIT_FAILURE cleanly aborts the transfer
    without mutating balances or saving transaction records.
    """
    sim = BankingSimulator(seed_default_fixtures=True)

    alice_before = sim.get_balance("acc_alice_chk")
    bob_before = sim.get_balance("acc_bob_chk")
    tx_count_before = len(sim.get_transactions("acc_alice_chk"))

    # Inject failure
    sim.inject_failure(FailureMode.PRE_COMMIT_FAILURE)

    result = sim.transfer("acc_alice_chk", "acc_bob_chk", Decimal("2000.00"), idempotency_key="retry_tx_1")

    assert result.success is False
    assert result.error_code == ErrorCode.SIMULATED_FAILURE
    assert "aborted before state commit" in result.message

    # Strict state consistency: balances and transactions remain untouched
    assert sim.get_balance("acc_alice_chk") == alice_before
    assert sim.get_balance("acc_bob_chk") == bob_before
    assert len(sim.get_transactions("acc_alice_chk")) == tx_count_before

    # Verify failed operation was NOT cached, so a subsequent retry after failure reset succeeds
    sim.inject_failure(FailureMode.NONE)

    retry_result = sim.transfer("acc_alice_chk", "acc_bob_chk", Decimal("2000.00"), idempotency_key="retry_tx_1")
    assert retry_result.success is True
    assert retry_result.error_code == ErrorCode.SUCCESS
    assert sim.get_balance("acc_alice_chk") == alice_before - Decimal("2000.00")
    assert sim.get_balance("acc_bob_chk") == bob_before + Decimal("2000.00")
