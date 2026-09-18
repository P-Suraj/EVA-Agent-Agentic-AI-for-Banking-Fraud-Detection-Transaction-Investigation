"""
Tests for Simulator Transfer Operations (src/banking_simulator/simulator.py).

Explicitly tests state-conservation invariants, frozen account behavior,
beneficiary ownership checks, and deterministic error codes.
"""

from decimal import Decimal
from banking_simulator.contracts import ErrorCode
from banking_simulator.models import Account, AccountStatus, AccountType, TransactionStatus
from banking_simulator.simulator import BankingSimulator


def test_successful_transfer_and_conservation_invariants():
    """
    Verify exact mathematical conservation:
    - source_after = source_before - amount
    - destination_after = destination_before + amount
    - (source_before + destination_before) == (source_after + destination_after)
    """
    sim = BankingSimulator(seed_default_fixtures=True)

    src_before = sim.get_balance("acc_alice_chk")
    dst_before = sim.get_balance("acc_bob_chk")
    assert src_before is not None and dst_before is not None

    amount = Decimal("2500.50")
    result = sim.transfer("acc_alice_chk", "acc_bob_chk", amount)

    assert result.success is True
    assert result.error_code == ErrorCode.SUCCESS
    assert result.data is not None
    assert result.data.status == TransactionStatus.POSTED
    assert result.data.amount == amount

    src_after = sim.get_balance("acc_alice_chk")
    dst_after = sim.get_balance("acc_bob_chk")
    assert src_after is not None and dst_after is not None

    # Invariants
    assert src_after == src_before - amount
    assert dst_after == dst_before + amount
    assert (src_before + dst_before) == (src_after + dst_after)


def test_frozen_source_account_rejected():
    """Verify transfer from a frozen source account is rejected without balance changes."""
    sim = BankingSimulator(seed_default_fixtures=True)

    src_before = sim.get_balance("acc_bob_frz")
    dst_before = sim.get_balance("acc_alice_chk")

    result = sim.transfer("acc_bob_frz", "acc_alice_chk", Decimal("500.00"))

    assert result.success is False
    assert result.error_code == ErrorCode.ACCOUNT_FROZEN
    assert "frozen" in result.message.lower()

    # Balances must be untouched
    assert sim.get_balance("acc_bob_frz") == src_before
    assert sim.get_balance("acc_alice_chk") == dst_before
    assert len(sim.get_transactions("acc_bob_frz")) == 0


def test_frozen_destination_account_rejected():
    """Verify transfer to a frozen destination account is rejected without balance changes."""
    sim = BankingSimulator(seed_default_fixtures=True)

    src_before = sim.get_balance("acc_alice_chk")
    dst_before = sim.get_balance("acc_bob_frz")

    result = sim.transfer("acc_alice_chk", "acc_bob_frz", Decimal("500.00"))

    assert result.success is False
    assert result.error_code == ErrorCode.ACCOUNT_FROZEN
    assert "destination account" in result.message.lower() and "frozen" in result.message.lower()

    # Balances must be untouched
    assert sim.get_balance("acc_alice_chk") == src_before
    assert sim.get_balance("acc_bob_frz") == dst_before
    assert len(sim.get_transactions("acc_alice_chk")) == 0


def test_invalid_amounts_return_deterministic_error_result():
    """
    Verify non-positive or float amounts return INVALID_AMOUNT without leaking exceptions.
    """
    sim = BankingSimulator(seed_default_fixtures=True)
    alice_before = sim.get_balance("acc_alice_chk")

    # Zero amount
    res_zero = sim.transfer("acc_alice_chk", "acc_bob_chk", Decimal("0.00"))
    assert res_zero.success is False
    assert res_zero.error_code == ErrorCode.INVALID_AMOUNT

    # Negative amount
    res_neg = sim.transfer("acc_alice_chk", "acc_bob_chk", Decimal("-100.00"))
    assert res_neg.success is False
    assert res_neg.error_code == ErrorCode.INVALID_AMOUNT

    # Float amount (disallowed for monetary safety)
    res_float = sim.transfer("acc_alice_chk", "acc_bob_chk", 150.75)
    assert res_float.success is False
    assert res_float.error_code == ErrorCode.INVALID_AMOUNT

    # String with letters
    res_str = sim.transfer("acc_alice_chk", "acc_bob_chk", "abc")
    assert res_str.success is False
    assert res_str.error_code == ErrorCode.INVALID_AMOUNT

    # Assert zero balance mutation
    assert sim.get_balance("acc_alice_chk") == alice_before


def test_insufficient_funds_rejection():
    """Verify transfers exceeding balance fail with INSUFFICIENT_FUNDS and zero mutation."""
    sim = BankingSimulator(seed_default_fixtures=True)

    src_before = sim.get_balance("acc_alice_chk")
    dst_before = sim.get_balance("acc_bob_chk")
    excessive_amount = Decimal("999999.00")

    result = sim.transfer("acc_alice_chk", "acc_bob_chk", excessive_amount)

    assert result.success is False
    assert result.error_code == ErrorCode.INSUFFICIENT_FUNDS
    assert sim.get_balance("acc_alice_chk") == src_before
    assert sim.get_balance("acc_bob_chk") == dst_before
    assert len(sim.get_transactions("acc_alice_chk")) == 0


def test_currency_mismatch_rejection():
    """Verify currency mismatch rejects transfer without balance mutation."""
    sim = BankingSimulator(seed_default_fixtures=True)

    # Inject an account with USD
    sim._accounts["acc_usd"] = Account(
        account_id="acc_usd",
        user_id="user_001",
        account_type=AccountType.CHECKING,
        currency="USD",
        balance=Decimal("1000.00"),
        status=AccountStatus.ACTIVE,
    )

    result = sim.transfer("acc_alice_chk", "acc_usd", Decimal("100.00"), currency="INR")
    assert result.success is False
    assert result.error_code == ErrorCode.CURRENCY_MISMATCH


def test_nonexistent_account_rejection():
    sim = BankingSimulator(seed_default_fixtures=True)

    res_src = sim.transfer("nonexistent_src", "acc_bob_chk", Decimal("100.00"))
    assert res_src.success is False
    assert res_src.error_code == ErrorCode.ACCOUNT_NOT_FOUND

    res_dst = sim.transfer("acc_alice_chk", "nonexistent_dst", Decimal("100.00"))
    assert res_dst.success is False
    assert res_dst.error_code == ErrorCode.ACCOUNT_NOT_FOUND


def test_beneficiary_transfer_success_and_ownership_checks():
    """
    Verify beneficiary transfer verifies owner_user_id and status.
    """
    sim = BankingSimulator(seed_default_fixtures=True)

    alice_before = sim.get_balance("acc_alice_chk")
    bob_before = sim.get_balance("acc_bob_chk")

    # 1. Valid transfer: Alice owns ben_bob_01 which is VERIFIED and points to acc_bob_chk
    res_valid = sim.transfer_to_beneficiary(
        owner_user_id="user_001",
        source_account_id="acc_alice_chk",
        beneficiary_id="ben_bob_01",
        amount=Decimal("1500.00"),
    )
    assert res_valid.success is True
    assert res_valid.error_code == ErrorCode.SUCCESS
    assert sim.get_balance("acc_alice_chk") == alice_before - Decimal("1500.00")
    assert sim.get_balance("acc_bob_chk") == bob_before + Decimal("1500.00")

    # 2. Ownership mismatch: Bob (user_002) tries to use Alice's beneficiary
    res_mismatch = sim.transfer_to_beneficiary(
        owner_user_id="user_002",
        source_account_id="acc_bob_chk",
        beneficiary_id="ben_bob_01",
        amount=Decimal("100.00"),
    )
    assert res_mismatch.success is False
    assert res_mismatch.error_code == ErrorCode.BENEFICIARY_OWNERSHIP_MISMATCH

    # 3. Unverified / pending beneficiary: ben_charlie_02 has status PENDING
    res_pending = sim.transfer_to_beneficiary(
        owner_user_id="user_001",
        source_account_id="acc_alice_chk",
        beneficiary_id="ben_charlie_02",
        amount=Decimal("100.00"),
    )
    assert res_pending.success is False
    assert res_pending.error_code == ErrorCode.BENEFICIARY_NOT_VERIFIED

    # 4. Non-existent beneficiary
    res_none = sim.transfer_to_beneficiary(
        owner_user_id="user_001",
        source_account_id="acc_alice_chk",
        beneficiary_id="ben_unknown",
        amount=Decimal("100.00"),
    )
    assert res_none.success is False
    assert res_none.error_code == ErrorCode.BENEFICIARY_NOT_FOUND
