"""
Tests for Simulator Read Operations (src/banking_simulator/simulator.py).
"""

from decimal import Decimal
from banking_simulator.models import AccountStatus, CardStatus, UserStatus
from banking_simulator.simulator import BankingSimulator


def test_read_existing_entities():
    sim = BankingSimulator(seed_default_fixtures=True)

    user = sim.get_user("user_001")
    assert user is not None
    assert user.name == "Alice Smith"
    assert user.status == UserStatus.ACTIVE

    account = sim.get_account("acc_alice_chk")
    assert account is not None
    assert account.user_id == "user_001"
    assert account.balance == Decimal("10000.00")
    assert account.status == AccountStatus.ACTIVE

    balance = sim.get_balance("acc_alice_chk")
    assert balance == Decimal("10000.00")

    card = sim.get_card("card_alice_01")
    assert card is not None
    assert card.user_id == "user_001"
    assert card.status == CardStatus.ACTIVE


def test_read_nonexistent_entities_return_none():
    sim = BankingSimulator(seed_default_fixtures=True)

    assert sim.get_user("nonexistent_user") is None
    assert sim.get_account("nonexistent_acc") is None
    assert sim.get_balance("nonexistent_acc") is None
    assert sim.get_card("nonexistent_card") is None
    assert sim.get_beneficiary("user_001", "nonexistent_ben") is None


def test_read_preserves_ownership_relationships():
    """Verify that beneficiary lookups require matching owner_user_id."""
    sim = BankingSimulator(seed_default_fixtures=True)

    # Bob is Alice's (user_001) beneficiary
    ben_for_alice = sim.get_beneficiary("user_001", "ben_bob_01")
    assert ben_for_alice is not None
    assert ben_for_alice.owner_user_id == "user_001"

    # Querying Alice's beneficiary under Bob's user_id must return None
    ben_for_bob = sim.get_beneficiary("user_002", "ben_bob_01")
    assert ben_for_bob is None


def test_simulator_instance_isolation():
    """Verify two simulator instances do not share mutable state."""
    sim1 = BankingSimulator(seed_default_fixtures=True)
    sim2 = BankingSimulator(seed_default_fixtures=True)

    sim1.transfer("acc_alice_chk", "acc_bob_chk", Decimal("1000.00"))
    assert sim1.get_balance("acc_alice_chk") == Decimal("9000.00")
    # sim2 must remain at initial 10000.00
    assert sim2.get_balance("acc_alice_chk") == Decimal("10000.00")
