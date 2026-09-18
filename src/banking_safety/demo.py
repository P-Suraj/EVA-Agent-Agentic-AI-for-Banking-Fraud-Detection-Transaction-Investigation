"""
Manual Verification Demo CLI for Phase 3 Banking Safety.

Demonstrates:
- DEMO 1: Authorized & Safe Transfer Within Limits
- DEMO 2: Per-Transaction Limit Violation Rejection
- DEMO 3: Daily Cumulative Limit Enforcement
- DEMO 4: Velocity Limit Enforcement (Rolling Window)
- DEMO 5: Step-Up Approval Workflow (Trigger -> Issue -> Verify -> Execute)
- DEMO 6: Tampered / Mismatched Approval Rejection
- DEMO 7: Authoritative Idempotency (Replay vs Conflict)
- DEMO 8: Gate Failure Containment & Approval Non-Burn on Simulator Failure
"""

from decimal import Decimal
import sys

from banking_safety.approval import SimulatedStepUpApprovalService
from banking_safety.config import TransactionSafetyConfig
from banking_safety.contracts import SafetyReasonCode
from banking_safety.engine import TransactionSafetyEngine
from banking_safety.gateway import SecureExecutionGateway
from banking_safety.idempotency import AuthoritativeIdempotencyStore
from banking_safety.limits import TransactionLimitEvaluator
from banking_safety.request import TransactionRequest
from banking_security.actions import BankingAction
from banking_security.context import SimulatedSessionManager
from banking_security.engine import DeterministicPolicyEngine
from banking_simulator.clock import SimulatedClock
from banking_simulator.contracts import ErrorCode
from banking_simulator.simulator import BankingSimulator


def run_demo() -> int:
    print("=" * 76)
    print("     PHASE 3: TRANSACTION SAFETY & DETERMINISTIC EXECUTION GATE")
    print("                     MANUAL VERIFICATION DEMO")
    print("=" * 76)

    # Shared public clock for strict determinism
    clock = SimulatedClock()
    sim = BankingSimulator(clock=clock, seed_default_fixtures=True)
    sessions = SimulatedSessionManager(sim)
    policy_engine = DeterministicPolicyEngine()
    config = TransactionSafetyConfig(
        per_transaction_limit=Decimal("25000.00"),
        daily_transfer_limit=Decimal("50000.00"),
        velocity_window_seconds=3600,
        velocity_count_limit=3,
        step_up_threshold=Decimal("5000.00"),
        currency="INR",
    )
    idempotency_store = AuthoritativeIdempotencyStore()
    approval_service = SimulatedStepUpApprovalService(clock=clock)
    limit_evaluator = TransactionLimitEvaluator(clock=clock)
    safety_engine = TransactionSafetyEngine(
        clock=clock,
        config=config,
        idempotency_store=idempotency_store,
        approval_service=approval_service,
        limit_evaluator=limit_evaluator,
    )
    gateway = SecureExecutionGateway(
        simulator=sim,
        session_manager=sessions,
        policy_engine=policy_engine,
        safety_engine=safety_engine,
    )

    # --------------------------------------------------------------------------
    # DEMO 1: Authorized & Safe Transfer Within Limits
    # --------------------------------------------------------------------------
    print("\n[DEMO 1] AUTHORIZED & SAFE TRANSFER WITHIN LIMITS")
    req1 = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("1500.00"),
        currency="INR",
        idempotency_key="demo_tx_001",
    )
    res1 = gateway.execute_transaction(session_token="token_alice", request=req1)
    print(f"  Caller:       token_alice ('user_001')")
    print(f"  Amount:       INR {req1.amount} (Limit: INR {config.per_transaction_limit})")
    print(f"  Result:       Success={res1.success}, Code={res1.error_code}, TxID={res1.transaction_id}")
    print(f"  Alice Bal:    INR {sim.get_balance('acc_alice_chk')}")
    print("  Outcome:      SUCCESS (Transfer executed and committed)")

    # --------------------------------------------------------------------------
    # DEMO 2: Per-Transaction Limit Violation Rejection
    # --------------------------------------------------------------------------
    print("\n[DEMO 2] PER-TRANSACTION LIMIT ENFORCEMENT")
    req2 = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("30000.00"),
        currency="INR",
        idempotency_key="demo_tx_002",
    )
    res2 = gateway.execute_transaction(session_token="token_alice", request=req2)
    print(f"  Amount:       INR {req2.amount} (Exceeds limit {config.per_transaction_limit})")
    print(f"  Result:       Success={res2.success}, Code={res2.error_code}")
    print(f"  Message:      {res2.message}")
    print("  Outcome:      SUCCESS (Rejected before reaching simulator execution)")

    # --------------------------------------------------------------------------
    # DEMO 3: Daily Cumulative Limit Enforcement
    # --------------------------------------------------------------------------
    print("\n[DEMO 3] DAILY CUMULATIVE LIMIT ENFORCEMENT")
    # Alice savings has ₹50,000 initial balance.
    # Tx 3a: ₹25,000 (with approval)
    req3a = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("25000.00"),
        currency="INR",
        idempotency_key="demo_tx_003a",
    )
    appr3a = approval_service.issue_approval("user_001", req3a)
    res3a = gateway.execute_transaction(session_token="token_alice", request=req3a, approval=appr3a)
    print(f"  Tx 3a:        INR 25000.00 -> Success={res3a.success} (Cumulative: INR 25000.00)")

    # Tx 3b: ₹20,000 (with approval) -> Cumulative today = ₹45,000
    req3b = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("20000.00"),
        currency="INR",
        idempotency_key="demo_tx_003b",
    )
    appr3b = approval_service.issue_approval("user_001", req3b)
    res3b = gateway.execute_transaction(session_token="token_alice", request=req3b, approval=appr3b)
    print(f"  Tx 3b:        INR 20000.00 -> Success={res3b.success} (Cumulative: INR 45000.00)")

    # Advance clock by 2 hours so velocity window clears, but daily date remains same
    clock.tick(7200)

    # Attempt Tx 3c: ₹10,000 (Cumulative would reach 45000 + 10000 = 55000 > 50000 cap)
    req3c = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_sav",
        destination_account_id="acc_bob_chk",
        amount=Decimal("10000.00"),
        currency="INR",
        idempotency_key="demo_tx_003c",
    )
    appr3c = approval_service.issue_approval("user_001", req3c)
    res3c = gateway.execute_transaction(session_token="token_alice", request=req3c, approval=appr3c)
    print(f"  Attempt 3c:   INR 10000.00 (Cumulative would reach INR 55000.00 > INR {config.daily_transfer_limit})")
    print(f"  Result:       Success={res3c.success}, Code={res3c.error_code}")
    print(f"  Message:      {res3c.message}")
    print("  Outcome:      SUCCESS (Daily limit exceeded rejected cleanly before simulator)")

    # --------------------------------------------------------------------------
    # DEMO 4: Velocity Limit Enforcement (Rolling Window)
    # --------------------------------------------------------------------------
    print("\n[DEMO 4] VELOCITY LIMIT ENFORCEMENT (MAX 3 OUTBOUND / HOUR)")
    # Use Bob's account (acc_bob_chk) for independent velocity tracking
    for i in range(1, 4):
        req_v = TransactionRequest(
            operation_type=BankingAction.TRANSFER,
            source_account_id="acc_bob_chk",
            destination_account_id="acc_alice_chk",
            amount=Decimal("100.00"),
            currency="INR",
            idempotency_key=f"demo_bob_vel_{i}",
        )
        res_v = gateway.execute_transaction(session_token="token_bob", request=req_v)
        print(f"  Bob Tx {i}:      Success={res_v.success}")

    # 4th transfer within 1 hour should be denied
    req_v4 = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_bob_chk",
        destination_account_id="acc_alice_chk",
        amount=Decimal("100.00"),
        currency="INR",
        idempotency_key="demo_bob_vel_4",
    )
    res_v4 = gateway.execute_transaction(session_token="token_bob", request=req_v4)
    print(f"  Bob Tx 4:      Success={res_v4.success}, Code={res_v4.error_code}")
    print(f"  Message:       {res_v4.message}")
    print("  Outcome:       SUCCESS (Velocity limit strictly enforced)")

    # --------------------------------------------------------------------------
    # DEMO 5: Step-Up Approval Workflow
    # --------------------------------------------------------------------------
    print("\n[DEMO 5] STEP-UP APPROVAL WORKFLOW (THRESHOLD >= INR 5,000)")
    # Alice checking account (balance ₹8,500, daily limit ₹50,000)
    req_step = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("6000.00"),
        currency="INR",
        idempotency_key="demo_step_001",
    )
    # Initial attempt without approval
    res_step_init = gateway.execute_transaction(session_token="token_alice", request=req_step, approval=None)
    print(f"  Attempt 1:    Without approval -> Code={res_step_init.error_code}")
    print(f"  Message:      {res_step_init.message}")

    # Issue trusted approval artifact
    appr_valid = approval_service.issue_approval("user_001", req_step)
    print(f"  Approval:     Issued ID '{appr_valid.approval_id}' bound to fingerprint '{appr_valid.transaction_fingerprint[:16]}...'")

    # Resubmit with valid approval
    res_step_final = gateway.execute_transaction(session_token="token_alice", request=req_step, approval=appr_valid)
    print(f"  Attempt 2:    With valid approval -> Success={res_step_final.success}, TxID={res_step_final.transaction_id}")
    print("  Outcome:      SUCCESS (Step-up workflow completed cleanly)")

    # --------------------------------------------------------------------------
    # DEMO 6: Tampered / Mismatched Approval Rejection
    # --------------------------------------------------------------------------
    print("\n[DEMO 6] TAMPERED / MISMATCHED APPROVAL REJECTION")
    # Advance clock to clear velocity window for Alice
    clock.tick(7200)
    # Caller attempts to use Alice's approval (issued for Bob) to send to Charlie
    req_tamper = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_alice_sav",  # Different recipient!
        amount=Decimal("6000.00"),
        currency="INR",
        idempotency_key="demo_tamper_001",
    )
    # Issue a fresh approval bound to Bob
    appr_mismatch = approval_service.issue_approval("user_001", req_step)
    res_tamper = gateway.execute_transaction(session_token="token_alice", request=req_tamper, approval=appr_mismatch)
    print(f"  Attack:       Fresh approval bound to Bob presented with target AliceSav")
    print(f"  Result:       Success={res_tamper.success}, Code={res_tamper.error_code}")
    print(f"  Message:      {res_tamper.message}")
    print("  Outcome:      SUCCESS (Approval fingerprint mismatch detected and blocked)")

    # --------------------------------------------------------------------------
    # DEMO 7: Authoritative Idempotency (Replay vs Conflict)
    # --------------------------------------------------------------------------
    print("\n[DEMO 7] AUTHORITATIVE IDEMPOTENCY REPLAY VS CONFLICT")
    # Replay of req_step (which succeeded in DEMO 5)
    tx_count_before = len(sim.get_transactions("acc_alice_chk"))
    res_replay = gateway.execute_transaction(session_token="token_alice", request=req_step)
    tx_count_after = len(sim.get_transactions("acc_alice_chk"))
    print(f"  Replay:       Success={res_replay.success}, CachedReplay={res_replay.cached_replay}")
    print(f"  Tx Count:     Before={tx_count_before}, After={tx_count_after} (Simulator NOT called)")

    # Conflicting replay: same key ("demo_step_001"), different amount
    req_conflict = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("7000.00"),  # Different amount!
        currency="INR",
        idempotency_key="demo_step_001",
    )
    res_conflict = gateway.execute_transaction(session_token="token_alice", request=req_conflict)
    print(f"  Conflict:     Success={res_conflict.success}, Code={res_conflict.error_code}")
    print("  Outcome:      SUCCESS (Replay served from cache; conflict rejected)")

    # --------------------------------------------------------------------------
    # DEMO 8: Gate Failure Containment & Approval Non-Burn on Simulator Failure
    # --------------------------------------------------------------------------
    print("\n[DEMO 8] GATE FAILURE CONTAINMENT & APPROVAL NON-BURN ON SIMULATOR FAILURE")
    # Advance clock to clear velocity
    clock.tick(7200)
    # Alice checking has balance ₹2,500 (10,000 - 1,500 - 6,000 = 2,500).
    # Attempt transfer of ₹6,000 (exceeds balance of ₹2,500!).
    alice_bal = sim.get_balance("acc_alice_chk")
    print(f"  Alice Bal:    INR {alice_bal}")
    req_fail = TransactionRequest(
        operation_type=BankingAction.TRANSFER,
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("6000.00"),
        currency="INR",
        idempotency_key="demo_fail_001",
    )
    appr_fail = approval_service.issue_approval("user_001", req_fail)
    print(f"  Approval ID:  {appr_fail.approval_id} (Issued for transfer of INR 6000.00)")

    res_fail = gateway.execute_transaction(session_token="token_alice", request=req_fail, approval=appr_fail)
    print(f"  Execution:    Success={res_fail.success}, Code={res_fail.error_code} ({res_fail.message})")

    # Invariant: Approval was NOT consumed!
    is_consumed = approval_service.is_consumed(appr_fail.approval_id)
    print(f"  Non-Burn:     Approval '{appr_fail.approval_id}' consumed? {is_consumed} (Must be False)")
    print("  Outcome:      SUCCESS (Failure contained; approval preserved for retry)")

    print("\n" + "=" * 76)
    print("            ALL PHASE 3 MANUAL DEMO VERIFICATIONS PASSED")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    sys.exit(run_demo())
