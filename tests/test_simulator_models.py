"""
Tests for Synthetic Banking Simulator Domain Models (src/banking_simulator/models.py).
"""

from decimal import Decimal
import pytest
from pydantic import ValidationError

from banking_simulator.models import (
    Account,
    AccountStatus,
    AccountType,
    Beneficiary,
    BeneficiaryStatus,
    Card,
    CardStatus,
    Transaction,
    TransactionStatus,
    TransactionType,
    User,
    UserStatus,
)


def test_user_model_valid():
    user = User(user_id="u_001", name="Alice", status=UserStatus.ACTIVE)
    assert user.user_id == "u_001"
    assert user.name == "Alice"
    assert user.status == UserStatus.ACTIVE


def test_user_model_extra_forbid():
    with pytest.raises(ValidationError):
        User(user_id="u_001", name="Alice", unexpected="value")  # type: ignore


def test_account_model_decimal_exactness():
    """Verify that Account balance uses exact Decimal arithmetic and rejects invalid inputs."""
    acc = Account(
        account_id="acc_001",
        user_id="u_001",
        account_type=AccountType.CHECKING,
        currency="INR",
        balance=Decimal("1234.56"),
        status=AccountStatus.ACTIVE,
    )
    assert isinstance(acc.balance, Decimal)
    assert acc.balance == Decimal("1234.56")


def test_account_model_negative_balance_rejected():
    with pytest.raises(ValidationError):
        Account(
            account_id="acc_001",
            user_id="u_001",
            account_type=AccountType.CHECKING,
            currency="INR",
            balance=Decimal("-10.00"),
            status=AccountStatus.ACTIVE,
        )


def test_beneficiary_model():
    ben = Beneficiary(
        beneficiary_id="ben_001",
        owner_user_id="u_001",
        name="Bob",
        account_reference="acc_bob",
        status=BeneficiaryStatus.VERIFIED,
    )
    assert ben.beneficiary_id == "ben_001"
    assert ben.owner_user_id == "u_001"
    assert ben.status == BeneficiaryStatus.VERIFIED


def test_transaction_model_exact_decimal():
    tx = Transaction(
        transaction_id="tx_0001",
        transaction_type=TransactionType.TRANSFER,
        source_account_id="acc_1",
        destination_account_id="acc_2",
        amount=Decimal("100.50"),
        currency="INR",
        status=TransactionStatus.POSTED,
        timestamp="2026-01-01T12:00:00+00:00",
    )
    assert tx.amount == Decimal("100.50")
    assert tx.status == TransactionStatus.POSTED


def test_transaction_model_non_positive_amount_rejected():
    with pytest.raises(ValidationError):
        Transaction(
            transaction_id="tx_0001",
            transaction_type=TransactionType.TRANSFER,
            source_account_id="acc_1",
            destination_account_id="acc_2",
            amount=Decimal("0.00"),
            currency="INR",
            status=TransactionStatus.POSTED,
            timestamp="2026-01-01T12:00:00+00:00",
        )


def test_card_model():
    card = Card(
        card_id="c_001",
        user_id="u_001",
        account_id="acc_001",
        card_number_masked="4111-XXXX-XXXX-1111",
        status=CardStatus.ACTIVE,
    )
    assert card.card_id == "c_001"
    assert card.status == CardStatus.ACTIVE
