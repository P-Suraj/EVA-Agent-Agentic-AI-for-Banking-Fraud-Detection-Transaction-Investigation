"""
Tests for Secure Banking Gateway Facade (src/banking_security/gateway.py).
"""

from decimal import Decimal
from banking_simulator.contracts import ErrorCode
from banking_simulator.models import CardStatus
from banking_simulator.simulator import BankingSimulator
from banking_security.gateway import SecureBankingGateway


def test_gateway_read_operations_authorized():
    sim = BankingSimulator(seed_default_fixtures=True)
    gateway = SecureBankingGateway(simulator=sim)

    # 1. Account read
    res_acc = gateway.get_account("token_alice", "acc_alice_chk")
    assert res_acc.success is True
    assert res_acc.data is not None
    assert res_acc.data.account_id == "acc_alice_chk"

    # 2. Balance read
    res_bal = gateway.get_balance("token_alice", "acc_alice_chk")
    assert res_bal.success is True
    assert res_bal.data == Decimal("10000.00")

    # 3. Card read
    res_card = gateway.get_card("token_alice", "card_alice_01")
    assert res_card.success is True
    assert res_card.data is not None
    assert res_card.data.card_id == "card_alice_01"

    # 4. Beneficiary read
    res_ben = gateway.get_beneficiary("token_alice", "ben_bob_01")
    assert res_ben.success is True
    assert res_ben.data is not None
    assert res_ben.data.beneficiary_id == "ben_bob_01"

    # 5. Transactions read
    res_txs = gateway.get_transactions("token_alice", "acc_alice_chk")
    assert res_txs.success is True
    assert isinstance(res_txs.data, list)


def test_gateway_freeze_card_authorized():
    sim = BankingSimulator(seed_default_fixtures=True)
    gateway = SecureBankingGateway(simulator=sim)

    res = gateway.freeze_card("token_alice", "card_alice_01")
    assert res.success is True
    assert res.data is not None
    assert res.data.status == CardStatus.FROZEN

    # Repeat freeze returns simulator CARD_ALREADY_FROZEN
    res_repeat = gateway.freeze_card("token_alice", "card_alice_01")
    assert res_repeat.success is False
    assert res_repeat.error_code == ErrorCode.CARD_ALREADY_FROZEN


def test_gateway_transfer_to_beneficiary_authorized():
    sim = BankingSimulator(seed_default_fixtures=True)
    gateway = SecureBankingGateway(simulator=sim)

    alice_before = sim.get_balance("acc_alice_chk")
    bob_before = sim.get_balance("acc_bob_chk")

    res = gateway.transfer_to_beneficiary(
        session_token="token_alice",
        source_account_id="acc_alice_chk",
        beneficiary_id="ben_bob_01",
        amount=Decimal("1200.00"),
    )

    assert res.success is True
    assert res.error_code == ErrorCode.SUCCESS
    assert sim.get_balance("acc_alice_chk") == alice_before - Decimal("1200.00")
    assert sim.get_balance("acc_bob_chk") == bob_before + Decimal("1200.00")


def test_gateway_transfer_to_beneficiary_unauthorized():
    sim = BankingSimulator(seed_default_fixtures=True)
    gateway = SecureBankingGateway(simulator=sim)

    # Bob tries to use Alice's beneficiary
    res = gateway.transfer_to_beneficiary(
        session_token="token_bob",
        source_account_id="acc_bob_chk",
        beneficiary_id="ben_bob_01",
        amount=Decimal("100.00"),
    )

    assert res.success is False
    assert res.error_code == ErrorCode.PERMISSION_DENIED
