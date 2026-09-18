"""
Tests for TransactionRequest Contract, Canonicalization, and Fingerprinting.
"""

from decimal import Decimal
import pytest
from pydantic import ValidationError

from banking_safety.request import TransactionRequest
from banking_security.actions import BankingAction


def test_valid_direct_transfer_request():
    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("1500.00"),
        currency="INR",
        idempotency_key="key_001",
    )
    assert req.operation_type == BankingAction.TRANSFER
    assert req.source_account_id == "acc_alice_chk"
    assert req.destination_account_id == "acc_bob_chk"
    assert req.beneficiary_id is None
    assert req.amount == Decimal("1500.00")
    assert req.currency == "INR"
    assert req.idempotency_key == "key_001"
    assert req.canonical_amount_str == "1500.00"


def test_valid_beneficiary_transfer_request():
    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER_TO_BENEFICIARY,
        source_account_id="acc_alice_chk",
        beneficiary_id="ben_alice_bob",
        amount=Decimal("250.50"),
        currency="INR",
        idempotency_key="key_002",
    )
    assert req.operation_type == BankingAction.TRANSFER_TO_BENEFICIARY
    assert req.beneficiary_id == "ben_alice_bob"
    assert req.destination_account_id is None
    assert req.target_reference == "ben_alice_bob"


def test_missing_or_empty_idempotency_key_rejected():
    # Missing key
    with pytest.raises(ValidationError):
        TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",
            amount=Decimal("100.00"),
            currency="INR",
        )

    # Empty string
    with pytest.raises(ValidationError):
        TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",
            amount=Decimal("100.00"),
            currency="INR",
            idempotency_key="",
        )

    # Whitespace string
    with pytest.raises(ValidationError):
        TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",
            amount=Decimal("100.00"),
            currency="INR",
            idempotency_key="   ",
        )


def test_sub_cent_precision_rejected_without_silent_rounding():
    # Amount with 3 decimal places must be rejected
    with pytest.raises(ValidationError) as exc_info:
        TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",
            amount=Decimal("100.123"),
            currency="INR",
            idempotency_key="key_003",
        )
    assert "precision beyond 2 decimal places" in str(exc_info.value)

    # Amount with 4 decimal places must also be rejected
    with pytest.raises(ValidationError):
        TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",
            amount=Decimal("50.0001"),
            currency="INR",
            idempotency_key="key_004",
        )


def test_equivalent_decimal_representations_canonicalized():
    # 100.1 and 100.10 represent the exact same monetary value
    req1 = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("100.1"),
        currency="INR",
        idempotency_key="key_005",
    )
    req2 = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("100.10"),
        currency="INR",
        idempotency_key="key_005",
    )
    assert req1.canonical_amount_str == "100.10"
    assert req2.canonical_amount_str == "100.10"
    assert req1.compute_fingerprint() == req2.compute_fingerprint()

    # Whole number 100
    req3 = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("100"),
        currency="INR",
        idempotency_key="key_005",
    )
    assert req3.canonical_amount_str == "100.00"


def test_float_amount_strictly_rejected():
    with pytest.raises(ValidationError) as exc_info:
        TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",
            amount=100.50,  # float
            currency="INR",
            idempotency_key="key_float",
        )
    assert "Floating-point amounts are strictly prohibited" in str(exc_info.value)


def test_zero_and_negative_amounts_rejected():
    with pytest.raises(ValidationError):
        TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",
            amount=Decimal("0.00"),
            currency="INR",
            idempotency_key="key_zero",
        )

    with pytest.raises(ValidationError):
        TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",
            amount=Decimal("-50.00"),
            currency="INR",
            idempotency_key="key_neg",
        )


def test_currency_format_validation():
    # Lowercase rejected
    with pytest.raises(ValidationError):
        TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",
            amount=Decimal("100.00"),
            currency="inr",
            idempotency_key="key_cur_1",
        )

    # Wrong length rejected
    with pytest.raises(ValidationError):
        TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",
            amount=Decimal("100.00"),
            currency="IN",
            idempotency_key="key_cur_2",
        )


def test_conflicting_or_missing_targets_rejected():
    # Both targets supplied
    with pytest.raises(ValidationError):
        TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",
            beneficiary_id="ben_alice_bob",
            amount=Decimal("100.00"),
            currency="INR",
            idempotency_key="key_both",
        )

    # Neither target supplied
    with pytest.raises(ValidationError):
        TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            amount=Decimal("100.00"),
            currency="INR",
            idempotency_key="key_none",
        )

    # Wrong target for TRANSFER_TO_BENEFICIARY
    with pytest.raises(ValidationError):
        TransactionRequest(
            operation_type=BankingAction.TRANSFER_TO_BENEFICIARY,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",  # Should be beneficiary_id
            amount=Decimal("100.00"),
            currency="INR",
            idempotency_key="key_wrong_target",
        )


def test_immutability_and_extra_forbid():
    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("100.00"),
        currency="INR",
        idempotency_key="key_immut",
    )

    # Mutation blocked
    with pytest.raises(ValidationError):
        req.amount = Decimal("200.00")

    # Extra fields blocked (e.g. caller trying to pass approved=True)
    with pytest.raises(ValidationError):
        TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_alice_chk",
            destination_account_id="acc_bob_chk",
            amount=Decimal("100.00"),
            currency="INR",
            idempotency_key="key_immut",
            approved=True,  # Extra field
        )


def test_deterministic_fingerprint_sensitivity():
    base = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("1000.00"),
        currency="INR",
        idempotency_key="k",
    )
    fp_base = base.compute_fingerprint()

    # Different amount -> different fingerprint
    req_amt = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("1000.01"),
        currency="INR",
        idempotency_key="k",
    )
    assert req_amt.compute_fingerprint() != fp_base

    # Different recipient -> different fingerprint
    req_dest = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_charlie_chk",
        amount=Decimal("1000.00"),
        currency="INR",
        idempotency_key="k",
    )
    assert req_dest.compute_fingerprint() != fp_base

    # Different source -> different fingerprint
    req_src = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("1000.00"),
        currency="INR",
        idempotency_key="k",
    )
    assert req_src.compute_fingerprint() != fp_base

    # Different currency -> different fingerprint
    req_cur = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("1000.00"),
        currency="USD",
        idempotency_key="k",
    )
    assert req_cur.compute_fingerprint() != fp_base
