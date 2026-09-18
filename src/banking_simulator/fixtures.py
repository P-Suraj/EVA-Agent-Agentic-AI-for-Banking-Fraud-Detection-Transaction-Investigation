"""
Deterministic Default Fixtures for Synthetic Banking Simulator.

Provides standard initial entities for reproducible testing.
All balances strictly use exact Decimal representation.
"""

from decimal import Decimal
from banking_simulator.models import (
    Account,
    AccountStatus,
    AccountType,
    Beneficiary,
    BeneficiaryStatus,
    Card,
    CardStatus,
    User,
    UserStatus,
)


def get_default_users() -> dict[str, User]:
    users = [
        User(user_id="user_001", name="Alice Smith", status=UserStatus.ACTIVE),
        User(user_id="user_002", name="Bob Jones", status=UserStatus.ACTIVE),
    ]
    return {u.user_id: u for u in users}


def get_default_accounts() -> dict[str, Account]:
    accounts = [
        Account(
            account_id="acc_alice_chk",
            user_id="user_001",
            account_type=AccountType.CHECKING,
            currency="INR",
            balance=Decimal("10000.00"),
            status=AccountStatus.ACTIVE,
        ),
        Account(
            account_id="acc_alice_sav",
            user_id="user_001",
            account_type=AccountType.SAVINGS,
            currency="INR",
            balance=Decimal("50000.00"),
            status=AccountStatus.ACTIVE,
        ),
        Account(
            account_id="acc_bob_chk",
            user_id="user_002",
            account_type=AccountType.CHECKING,
            currency="INR",
            balance=Decimal("5000.00"),
            status=AccountStatus.ACTIVE,
        ),
        Account(
            account_id="acc_bob_frz",
            user_id="user_002",
            account_type=AccountType.CHECKING,
            currency="INR",
            balance=Decimal("2000.00"),
            status=AccountStatus.FROZEN,
        ),
    ]
    return {a.account_id: a for a in accounts}


def get_default_beneficiaries() -> dict[str, Beneficiary]:
    beneficiaries = [
        Beneficiary(
            beneficiary_id="ben_bob_01",
            owner_user_id="user_001",
            name="Bob Jones",
            account_reference="acc_bob_chk",
            status=BeneficiaryStatus.VERIFIED,
        ),
        Beneficiary(
            beneficiary_id="ben_charlie_02",
            owner_user_id="user_001",
            name="Charlie",
            account_reference="acc_nonexistent",
            status=BeneficiaryStatus.PENDING,
        ),
    ]
    return {b.beneficiary_id: b for b in beneficiaries}


def get_default_cards() -> dict[str, Card]:
    cards = [
        Card(
            card_id="card_alice_01",
            user_id="user_001",
            account_id="acc_alice_chk",
            card_number_masked="4111-XXXX-XXXX-1111",
            status=CardStatus.ACTIVE,
        ),
        Card(
            card_id="card_bob_01",
            user_id="user_002",
            account_id="acc_bob_chk",
            card_number_masked="4111-XXXX-XXXX-2222",
            status=CardStatus.ACTIVE,
        ),
    ]
    return {c.card_id: c for c in cards}
