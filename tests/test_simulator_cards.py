"""
Tests for Simulator Card Operations (src/banking_simulator/simulator.py).
"""

from banking_simulator.contracts import ErrorCode
from banking_simulator.models import CardStatus
from banking_simulator.simulator import BankingSimulator


def test_freeze_card_success():
    sim = BankingSimulator(seed_default_fixtures=True)

    card = sim.get_card("card_alice_01")
    assert card is not None
    assert card.status == CardStatus.ACTIVE

    result = sim.freeze_card("card_alice_01")
    assert result.success is True
    assert result.error_code == ErrorCode.SUCCESS
    assert result.data is not None
    assert result.data.status == CardStatus.FROZEN

    # Verify state reflects frozen status
    updated_card = sim.get_card("card_alice_01")
    assert updated_card is not None
    assert updated_card.status == CardStatus.FROZEN


def test_freeze_already_frozen_card():
    sim = BankingSimulator(seed_default_fixtures=True)

    # First freeze
    sim.freeze_card("card_alice_01")

    # Repeat freeze
    result = sim.freeze_card("card_alice_01")
    assert result.success is False
    assert result.error_code == ErrorCode.CARD_ALREADY_FROZEN


def test_freeze_nonexistent_card():
    sim = BankingSimulator(seed_default_fixtures=True)

    result = sim.freeze_card("card_unknown")
    assert result.success is False
    assert result.error_code == ErrorCode.CARD_NOT_FOUND
