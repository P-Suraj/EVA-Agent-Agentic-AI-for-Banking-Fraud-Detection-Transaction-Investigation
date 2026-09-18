"""
Tests for Simulated Step-Up Approvals, Fingerprint Binding, and Non-Burn Semantics.
"""

from decimal import Decimal
import pytest

from banking_safety.approval import SimulatedStepUpApprovalService, StepUpApproval
from banking_safety.config import TransactionSafetyConfig
from banking_safety.contracts import SafetyReasonCode
from banking_safety.engine import TransactionSafetyEngine
from banking_safety.gateway import SecureExecutionGateway
from banking_safety.request import TransactionRequest
from banking_security.actions import BankingAction
from banking_simulator.clock import SimulatedClock
from banking_simulator.contracts import ErrorCode, FailureMode
from banking_simulator.simulator import BankingSimulator


def test_step_up_threshold_trigger():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    config = TransactionSafetyConfig(
        per_transaction_limit=Decimal("50000.00"),
        step_up_threshold=Decimal("10000.00"),
    )
    gateway = SecureExecutionGateway(
        simulator=sim,
        safety_engine=TransactionSafetyEngine(clock=clock, config=config),
    )

    # 1. Below threshold (₹9,999.99) -> No approval required -> ALLOW
    req_below = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("9999.99"),
        currency="INR",
        idempotency_key="step_below",
    )
    res_below = gateway.execute_transaction(session_token="token_alice", request=req_below)
    assert res_below.success is True

    # 2. Exactly at threshold (₹10,000.00) without approval -> STEP_UP_REQUIRED
    req_at = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("10000.00"),
        currency="INR",
        idempotency_key="step_at",
    )
    res_at = gateway.execute_transaction(session_token="token_alice", request=req_at)
    assert res_at.success is False
    assert res_at.error_code == SafetyReasonCode.STEP_UP_REQUIRED

    # 3. Above threshold (₹15,000.00) without approval -> STEP_UP_REQUIRED
    req_above = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("15000.00"),
        currency="INR",
        idempotency_key="step_above",
    )
    res_above = gateway.execute_transaction(session_token="token_alice", request=req_above)
    assert res_above.success is False
    assert res_above.error_code == SafetyReasonCode.STEP_UP_REQUIRED


def test_valid_approval_issuance_and_execution():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    config = TransactionSafetyConfig(
        per_transaction_limit=Decimal("50000.00"),
        step_up_threshold=Decimal("10000.00"),
    )
    approval_svc = SimulatedStepUpApprovalService(clock=clock)
    safety_engine = TransactionSafetyEngine(clock=clock, config=config, approval_service=approval_svc)
    gateway = SecureExecutionGateway(simulator=sim, safety_engine=safety_engine)

    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("15000.00"),
        currency="INR",
        idempotency_key="step_valid",
    )

    # Issue trusted approval for Alice ('user_001')
    approval = approval_svc.issue_approval("user_001", req)
    assert approval.principal_id == "user_001"
    assert approval.transaction_fingerprint == req.compute_fingerprint()

    # Execute with approval
    res = gateway.execute_transaction(session_token="token_alice", request=req, approval=approval)
    assert res.success is True
    assert res.transaction_id is not None

    # Invariant: Approval is marked consumed after success
    assert approval_svc.is_consumed(approval.approval_id) is True


def test_approval_mismatch_on_amount():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    approval_svc = SimulatedStepUpApprovalService(clock=clock)
    gateway = SecureExecutionGateway(
        simulator=sim,
        safety_engine=TransactionSafetyEngine(clock=clock, approval_service=approval_svc),
    )

    # Approval issued for ₹10,000
    req_10k = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("10000.00"),
        currency="INR",
        idempotency_key="k_10k",
    )
    approval = approval_svc.issue_approval("user_001", req_10k)

    # Caller presents that approval for ₹20,000 transfer
    req_20k = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("20000.00"),
        currency="INR",
        idempotency_key="k_20k",
    )
    res = gateway.execute_transaction(session_token="token_alice", request=req_20k, approval=approval)
    assert res.success is False
    assert res.error_code == SafetyReasonCode.APPROVAL_MISMATCH


def test_approval_mismatch_on_recipient():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    approval_svc = SimulatedStepUpApprovalService(clock=clock)
    gateway = SecureExecutionGateway(
        simulator=sim,
        safety_engine=TransactionSafetyEngine(clock=clock, approval_service=approval_svc),
    )

    # Approval issued to Bob
    req_bob = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("12000.00"),
        currency="INR",
        idempotency_key="k_bob_appr",
    )
    approval = approval_svc.issue_approval("user_001", req_bob)

    # Presented for Alice's other account as destination
    req_charlie = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_alice_chk",
        amount=Decimal("12000.00"),
        currency="INR",
        idempotency_key="k_charlie_appr",
    )
    res = gateway.execute_transaction(session_token="token_alice", request=req_charlie, approval=approval)
    assert res.success is False
    assert res.error_code == SafetyReasonCode.APPROVAL_MISMATCH


def test_approval_reuse_rejected():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    approval_svc = SimulatedStepUpApprovalService(clock=clock)
    gateway = SecureExecutionGateway(
        simulator=sim,
        safety_engine=TransactionSafetyEngine(clock=clock, approval_service=approval_svc),
    )

    req1 = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("12000.00"),
        currency="INR",
        idempotency_key="reuse_tx_1",
    )
    approval = approval_svc.issue_approval("user_001", req1)

    # First execution succeeds and consumes approval
    res1 = gateway.execute_transaction(session_token="token_alice", request=req1, approval=approval)
    assert res1.success is True

    # Advance clock and clear velocity window
    clock.tick(3601)

    # Attempt to reuse the consumed approval with a new transaction
    req2 = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("12000.00"),
        currency="INR",
        idempotency_key="reuse_tx_2",
    )
    res2 = gateway.execute_transaction(session_token="token_alice", request=req2, approval=approval)
    assert res2.success is False
    assert res2.error_code == SafetyReasonCode.APPROVAL_ALREADY_USED


def test_expired_approval_rejected():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    approval_svc = SimulatedStepUpApprovalService(clock=clock)
    gateway = SecureExecutionGateway(
        simulator=sim,
        safety_engine=TransactionSafetyEngine(clock=clock, approval_service=approval_svc),
    )

    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("12000.00"),
        currency="INR",
        idempotency_key="k_exp",
    )
    # Valid for 300 seconds (5 minutes)
    approval = approval_svc.issue_approval("user_001", req, valid_duration_seconds=300)

    # Advance clock by 301 seconds
    clock.tick(301)

    res = gateway.execute_transaction(session_token="token_alice", request=req, approval=approval)
    assert res.success is False
    assert res.error_code == SafetyReasonCode.APPROVAL_EXPIRED


def test_untrusted_manufactured_approval_rejected():
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    approval_svc = SimulatedStepUpApprovalService(clock=clock)
    gateway = SecureExecutionGateway(
        simulator=sim,
        safety_engine=TransactionSafetyEngine(clock=clock, approval_service=approval_svc),
    )

    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("12000.00"),
        currency="INR",
        idempotency_key="k_forged",
    )

    # Caller manufactures an ad-hoc StepUpApproval without the service
    forged_approval = StepUpApproval(
        approval_id="forged_999",
        principal_id="user_001",
        transaction_fingerprint=req.compute_fingerprint(),
        issued_at=clock.now_iso(),
        expires_at=None,
    )

    res = gateway.execute_transaction(session_token="token_alice", request=req, approval=forged_approval)
    assert res.success is False
    assert res.error_code == SafetyReasonCode.UNTRUSTED_APPROVAL


def test_approval_preserved_on_insufficient_funds():
    """
    Approval Non-Burn Invariant:
    If Layer 4 Simulator rejects due to INSUFFICIENT_FUNDS, the approval is NOT consumed.
    """
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    config = TransactionSafetyConfig(
        per_transaction_limit=Decimal("50000.00"),
        step_up_threshold=Decimal("10000.00"),
    )
    approval_svc = SimulatedStepUpApprovalService(clock=clock)
    safety_engine = TransactionSafetyEngine(clock=clock, config=config, approval_service=approval_svc)
    gateway = SecureExecutionGateway(simulator=sim, safety_engine=safety_engine)

    # Alice checking has ₹10,000. Attempt transfer of ₹12,000 from acc_alice_chk
    req = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("12000.00"),
        currency="INR",
        idempotency_key="non_burn_funds_key",
    )
    approval = approval_svc.issue_approval("user_001", req)

    # Execution fails at simulator due to insufficient funds
    res1 = gateway.execute_transaction(session_token="token_alice", request=req, approval=approval)
    assert res1.success is False
    assert res1.error_code == ErrorCode.INSUFFICIENT_FUNDS

    # Invariant: Approval is NOT consumed
    assert approval_svc.is_consumed(approval.approval_id) is False

    # Alice receives funds
    sim._accounts["acc_alice_chk"].balance += Decimal("10000.00")

    # Resubmitting with the EXACT SAME approval token now succeeds!
    res2 = gateway.execute_transaction(session_token="token_alice", request=req, approval=approval)
    assert res2.success is True
    assert res2.transaction_id is not None
    assert approval_svc.is_consumed(approval.approval_id) is True
