"""
Security Tests: Future Agent Threat Model, Confused-Deputy Mitigation, and Metrics Suite.
"""

from decimal import Decimal
from unittest.mock import patch
import pytest

from banking_safety.approval import SimulatedStepUpApprovalService
from banking_safety.config import TransactionSafetyConfig
from banking_safety.contracts import SafetyReasonCode
from banking_safety.engine import TransactionSafetyEngine
from banking_safety.gateway import SecureExecutionGateway
from banking_safety.request import TransactionRequest
from banking_security.actions import BankingAction
from banking_simulator.clock import SimulatedClock
from banking_simulator.contracts import ErrorCode, FailureMode
from banking_simulator.simulator import BankingSimulator


def test_threat_model_wrong_amount_never_silently_repaired():
    """
    Threat Model:
    User intent: "Transfer ₹5,000 to Bob"
    Future agent produces: amount = 50,000

    System must evaluate 50,000 against limits and step-up rules.
    It must NEVER assume ₹5,000 was intended or silently alter the transaction.
    """
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    config = TransactionSafetyConfig(
        per_transaction_limit=Decimal("25000.00"),
        step_up_threshold=Decimal("10000.00"),
    )
    gateway = SecureExecutionGateway(
        simulator=sim,
        safety_engine=TransactionSafetyEngine(clock=clock, config=config),
    )

    req_hallucinated = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("50000.00"),  # Hallucinated 10x amount
        currency="INR",
        idempotency_key="agent_wrong_amount",
    )

    res = gateway.execute_transaction(session_token="token_alice", request=req_hallucinated)
    # Must be denied because 50,000 > per_transaction_limit 25,000
    assert res.success is False
    assert res.error_code == SafetyReasonCode.PER_TRANSACTION_LIMIT_EXCEEDED
    # Invariant: No transfer of ₹5,000 or ₹50,000 occurred
    assert sim.get_balance("acc_alice_chk") == Decimal("10000.00")
    assert len(sim.get_transactions("acc_alice_chk")) == 0


def test_threat_model_wrong_recipient_blocked_by_approval_binding():
    """
    Threat Model:
    User intent: Transfer to Bob.
    User approves transaction for Bob.
    Agent hallucinates or maliciously substitutes Charlie ('acc_charlie_chk').

    The approval is bound to Bob. The safety gate must detect fingerprint mismatch
    and deny execution.
    """
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    config = TransactionSafetyConfig(
        per_transaction_limit=Decimal("50000.00"),
        step_up_threshold=Decimal("10000.00"),
    )
    approval_svc = SimulatedStepUpApprovalService(clock=clock)
    gateway = SecureExecutionGateway(
        simulator=sim,
        safety_engine=TransactionSafetyEngine(clock=clock, config=config, approval_service=approval_svc),
    )

    # Intended transfer to Bob: user approved this
    req_intended = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("15000.00"),
        currency="INR",
        idempotency_key="k_substitute",
    )
    approval_for_bob = approval_svc.issue_approval("user_001", req_intended)

    # Agent substitutes Charlie as destination
    req_substituted = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_charlie_chk",
        amount=Decimal("15000.00"),
        currency="INR",
        idempotency_key="k_substitute",
    )

    res = gateway.execute_transaction(
        session_token="token_alice",
        request=req_substituted,
        approval=approval_for_bob,
    )
    assert res.success is False
    assert res.error_code == SafetyReasonCode.APPROVAL_MISMATCH
    assert "fingerprint mismatch" in res.message


def test_confused_deputy_source_account_drain_attempt():
    """
    Threat Model:
    Caller presents Alice's token, but attempts to specify Bob's checking account
    as the source_account_id to drain Bob's funds.
    """
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    gateway = SecureExecutionGateway(simulator=sim, safety_engine=TransactionSafetyEngine(clock=clock))

    bob_before = sim.get_balance("acc_bob_chk")

    req_attack = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_bob_chk",  # Attacking Bob's account
        destination_account_id="acc_alice_chk",
        amount=Decimal("1000.00"),
        currency="INR",
        idempotency_key="k_confused_deputy",
    )

    res = gateway.execute_transaction(session_token="token_alice", request=req_attack)
    assert res.success is False
    assert res.error_code == ErrorCode.PERMISSION_DENIED
    assert sim.get_balance("acc_bob_chk") == bob_before


def test_security_metrics_calculation_suite():
    """
    Computes and verifies all 10 safety metrics defined in the Phase 3 evaluation plan:
    1. Wrong-Amount Execution Rate = 0.0
    2. Wrong-Recipient Execution Rate = 0.0
    3. Duplicate Execution Rate = 0.0
    4. Idempotency Conflict Bypass Rate = 0.0
    5. Transaction-Limit Bypass Rate = 0.0
    6. Approval Bypass Rate = 0.0
    7. Unauthorized Execution Rate = 0.0
    8. Partial-Mutation Rate = 0.0
    9. Pre-Execution Simulator Mutation Invocation Count = 0
    10. Safe-Failure Rate = 1.0 (100%)
    """
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    config = TransactionSafetyConfig(
        per_transaction_limit=Decimal("10000.00"),
        daily_transfer_limit=Decimal("20000.00"),
        step_up_threshold=Decimal("5000.00"),
        velocity_count_limit=2,
    )
    approval_svc = SimulatedStepUpApprovalService(clock=clock)
    gateway = SecureExecutionGateway(
        simulator=sim,
        safety_engine=TransactionSafetyEngine(clock=clock, config=config, approval_service=approval_svc),
    )

    metrics_counters = {
        "wrong_amount_attempts": 0,
        "wrong_amount_executions": 0,
        "wrong_recipient_attempts": 0,
        "wrong_recipient_executions": 0,
        "duplicate_attempts": 0,
        "duplicate_executions": 0,
        "conflict_attempts": 0,
        "conflict_bypasses": 0,
        "limit_bypass_attempts": 0,
        "limit_bypasses": 0,
        "approval_bypass_attempts": 0,
        "approval_bypasses": 0,
        "unauthorized_attempts": 0,
        "unauthorized_executions": 0,
        "failure_attempts": 0,
        "partial_mutations": 0,
        "error_attempts": 0,
        "safe_failures": 0,
        "pre_exec_denial_sim_invocations": 0,
    }

    # Helper to test denial and count simulator calls
    def evaluate_denial(token, req, approval=None, category=None):
        metrics_counters["error_attempts"] += 1
        if category:
            metrics_counters[f"{category}_attempts"] += 1

        with patch.object(sim, "_execute_transfer", wraps=sim._execute_transfer) as mock_sim:
            res = gateway.execute_transaction(token, req, approval=approval)
            if mock_sim.call_count > 0:
                metrics_counters["pre_exec_denial_sim_invocations"] += mock_sim.call_count

            if res.success is False and res.error_code is not None:
                metrics_counters["safe_failures"] += 1
            elif res.success is True and category:
                metrics_counters[f"{category}_executions"] += 1
            return res

    # 1. Unauthorized attempt
    req_unauth = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_bob_chk",
        destination_account_id="acc_alice_chk",
        amount=Decimal("100.00"),
        currency="INR",
        idempotency_key="m_unauth",
    )
    evaluate_denial("token_alice", req_unauth, category="unauthorized")

    # 2. Limit bypass attempt
    req_limit = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("15000.00"),  # > 10,000 per_tx_limit
        currency="INR",
        idempotency_key="m_limit",
    )
    evaluate_denial("token_alice", req_limit, category="limit_bypass")

    # 3. Approval bypass attempt (no approval)
    req_appr = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("6000.00"),  # >= 5,000 threshold
        currency="INR",
        idempotency_key="m_appr",
    )
    evaluate_denial("token_alice", req_appr, approval=None, category="approval_bypass")

    # 4. Wrong amount attack attempt
    req_wrong_amt = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("25000.00"),
        currency="INR",
        idempotency_key="m_wrong_amt",
    )
    evaluate_denial("token_alice", req_wrong_amt, category="wrong_amount")

    # 5. Wrong recipient attack attempt
    req_legit = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("6000.00"),
        currency="INR",
        idempotency_key="m_legit",
    )
    appr_legit = approval_svc.issue_approval("user_001", req_legit)
    req_tampered_recip = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_charlie_chk",
        amount=Decimal("6000.00"),
        currency="INR",
        idempotency_key="m_wrong_recip",
    )
    evaluate_denial("token_alice", req_tampered_recip, approval=appr_legit, category="wrong_recipient")

    # 6. Replay & Conflict metrics
    req_valid = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("500.00"),
        currency="INR",
        idempotency_key="m_valid_1",
    )
    res_valid = gateway.execute_transaction("token_alice", req_valid)
    assert res_valid.success is True

    # Replay attempt
    metrics_counters["duplicate_attempts"] += 1
    alice_bal_before_rep = sim.get_balance("acc_alice_chk")
    res_rep = gateway.execute_transaction("token_alice", req_valid)
    assert res_rep.cached_replay is True
    if sim.get_balance("acc_alice_chk") != alice_bal_before_rep:
        metrics_counters["duplicate_executions"] += 1

    # Conflict attempt
    req_conf = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("600.00"),
        currency="INR",
        idempotency_key="m_valid_1",
    )
    evaluate_denial("token_alice", req_conf, category="conflict")

    # 7. Partial mutation check on pre-commit failure
    metrics_counters["failure_attempts"] += 1
    sim.inject_failure(FailureMode.PRE_COMMIT_FAILURE)
    alice_bal_pre = sim.get_balance("acc_alice_chk")
    bob_bal_pre = sim.get_balance("acc_bob_chk")
    req_fail = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("200.00"),
        currency="INR",
        idempotency_key="m_inj_fail",
    )
    res_fail = gateway.execute_transaction("token_alice", req_fail)
    sim.inject_failure(FailureMode.NONE)

    assert res_fail.success is False
    if sim.get_balance("acc_alice_chk") != alice_bal_pre or sim.get_balance("acc_bob_chk") != bob_bal_pre:
        metrics_counters["partial_mutations"] += 1

    # Final Metric Verifications
    wrong_amount_rate = (
        metrics_counters["wrong_amount_executions"] / metrics_counters["wrong_amount_attempts"]
    )
    wrong_recipient_rate = (
        metrics_counters["wrong_recipient_executions"] / metrics_counters["wrong_recipient_attempts"]
    )
    duplicate_rate = (
        metrics_counters["duplicate_executions"] / metrics_counters["duplicate_attempts"]
    )
    conflict_bypass_rate = (
        metrics_counters["conflict_bypasses"] / metrics_counters["conflict_attempts"]
    )
    limit_bypass_rate = (
        metrics_counters["limit_bypasses"] / metrics_counters["limit_bypass_attempts"]
    )
    approval_bypass_rate = (
        metrics_counters["approval_bypasses"] / metrics_counters["approval_bypass_attempts"]
    )
    unauthorized_rate = (
        metrics_counters["unauthorized_executions"] / metrics_counters["unauthorized_attempts"]
    )
    partial_mutation_rate = (
        metrics_counters["partial_mutations"] / metrics_counters["failure_attempts"]
    )
    safe_failure_rate = (
        metrics_counters["safe_failures"] / metrics_counters["error_attempts"]
    )

    assert wrong_amount_rate == 0.0
    assert wrong_recipient_rate == 0.0
    assert duplicate_rate == 0.0
    assert conflict_bypass_rate == 0.0
    assert limit_bypass_rate == 0.0
    assert approval_bypass_rate == 0.0
    assert unauthorized_rate == 0.0
    assert partial_mutation_rate == 0.0
    assert safe_failure_rate == 1.0
    assert metrics_counters["pre_exec_denial_sim_invocations"] == 0
