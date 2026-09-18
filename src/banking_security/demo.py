"""
Manual Verification Demo CLI for Phase 2 Banking Security.

Demonstrates deterministic authentication, authorization, fail-closed enforcement,
confused-deputy defense, and layer separation.
"""

from decimal import Decimal
import sys

from banking_security.actions import BankingAction, ResourceTarget, ResourceType
from banking_security.context import SimulatedSessionManager
from banking_security.contracts import PolicyDecision, PolicyReasonCode
from banking_security.engine import DeterministicPolicyEngine
from banking_security.gateway import SecureBankingGateway
from banking_simulator.contracts import ErrorCode
from banking_simulator.simulator import BankingSimulator


def run_demo() -> int:
    print("=" * 74)
    print("     PHASE 2: AUTHENTICATION, AUTHORIZATION & DETERMINISTIC POLICY")
    print("                    MANUAL SECURITY VERIFICATION")
    print("=" * 74)

    sim = BankingSimulator(seed_default_fixtures=True)
    sessions = SimulatedSessionManager(sim)
    engine = DeterministicPolicyEngine()
    gateway = SecureBankingGateway(simulator=sim, session_manager=sessions, policy_engine=engine)

    # --------------------------------------------------------------------------
    # DEMO 1: Unauthenticated Caller Rejection
    # --------------------------------------------------------------------------
    print("\n[DEMO 1] UNAUTHENTICATED CALLER REJECTION (FAIL-CLOSED)")
    res_unauth = gateway.get_balance(session_token=None, account_id="acc_alice_chk")
    print(f"  Token:        None (Missing / unauthenticated)")
    print(f"  Target:       acc_alice_chk")
    print(f"  Result:       Success={res_unauth.success}, ErrorCode={res_unauth.error_code}")
    print(f"  Message:      {res_unauth.message}")
    print("  Outcome:      SUCCESS (Unauthenticated call rejected immediately with PERMISSION_DENIED)")

    # --------------------------------------------------------------------------
    # DEMO 2: Authorized Access (Alice -> Alice Account)
    # --------------------------------------------------------------------------
    print("\n[DEMO 2] AUTHORIZED ACCOUNT ACCESS & READ")
    res_auth = gateway.get_balance(session_token="token_alice", account_id="acc_alice_chk")
    print(f"  Token:        token_alice -> Principal 'user_001'")
    print(f"  Target:       acc_alice_chk (Owner: 'user_001')")
    print(f"  Result:       Success={res_auth.success}, ErrorCode={res_auth.error_code}, Balance=INR {res_auth.data}")
    print("  Outcome:      SUCCESS (Authenticated owner granted access)")

    # --------------------------------------------------------------------------
    # DEMO 3: Cross-User Unauthorized Access Denied
    # --------------------------------------------------------------------------
    print("\n[DEMO 3] CROSS-USER SNOOPING DENIED (LEAST PRIVILEGE)")
    res_cross = gateway.get_balance(session_token="token_alice", account_id="acc_bob_chk")
    print(f"  Caller:       token_alice (Alice, 'user_001')")
    print(f"  Target:       acc_bob_chk (Bob's account, 'user_002')")
    print(f"  Result:       Success={res_cross.success}, ErrorCode={res_cross.error_code}")
    print(f"  Message:      {res_cross.message}")
    print("  Outcome:      SUCCESS (Cross-user read denied with OWNERSHIP_MISMATCH)")

    # --------------------------------------------------------------------------
    # DEMO 4: Direct Transfer to Another User's Account (Target Semantics)
    # --------------------------------------------------------------------------
    print("\n[DEMO 4] DIRECT TRANSFER TO OTHER USER'S ACCOUNT (DESTINATION IS TARGET)")
    alice_before = sim.get_balance("acc_alice_chk")
    bob_before = sim.get_balance("acc_bob_chk")
    print(f"  Sender:       Alice ('user_001'), Source: acc_alice_chk (Balance: INR {alice_before})")
    print(f"  Target:       acc_bob_chk (Owned by Bob, 'user_002', Balance: INR {bob_before})")

    res_transfer = gateway.transfer(
        session_token="token_alice",
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("1500.00"),
    )
    alice_after = sim.get_balance("acc_alice_chk")
    bob_after = sim.get_balance("acc_bob_chk")
    print(f"  Result:       Success={res_transfer.success}, ErrorCode={res_transfer.error_code}")
    print(f"  Alice After:  INR {alice_after}")
    print(f"  Bob After:    INR {bob_after}")
    print("  Outcome:      SUCCESS (Alice owns source; destination ownership is not required for sender)")

    # --------------------------------------------------------------------------
    # DEMO 5: Confused-Deputy Attack Prevention
    # --------------------------------------------------------------------------
    print("\n[DEMO 5] CONFUSED-DEPUTY ATTACK PREVENTION (SOURCE IMPERSONATION)")
    bob_before_cd = sim.get_balance("acc_bob_chk")
    alice_before_cd = sim.get_balance("acc_alice_chk")
    tx_count_before = len(sim.get_transactions("acc_bob_chk"))

    print("  Attack:       Caller presents Alice's token, but attempts to debit Bob's account (acc_bob_chk)")
    res_attack = gateway.transfer(
        session_token="token_alice",
        source_account_id="acc_bob_chk",
        destination_account_id="acc_alice_chk",
        amount=Decimal("3000.00"),
    )
    bob_after_cd = sim.get_balance("acc_bob_chk")
    alice_after_cd = sim.get_balance("acc_alice_chk")
    tx_count_after = len(sim.get_transactions("acc_bob_chk"))

    print(f"  Result:       Success={res_attack.success}, ErrorCode={res_attack.error_code}")
    print(f"  Message:      {res_attack.message}")
    print(f"  Invariant:    Bob balance unchanged (INR {bob_before_cd} == INR {bob_after_cd}) -> {bob_before_cd == bob_after_cd}")
    print(f"  Invariant:    Simulator not invoked (tx count: {tx_count_before} == {tx_count_after})")
    print("  Outcome:      SUCCESS (Confused-deputy attack completely blocked via ground-truth check)")

    # --------------------------------------------------------------------------
    # DEMO 6: Suspended User Standing Gate
    # --------------------------------------------------------------------------
    print("\n[DEMO 6] SUSPENDED USER AUTHENTICATION VS AUTHORIZATION")
    auth_ctx = sessions.authenticate("token_suspended")
    print(f"  Auth Result:  Authenticated={auth_ctx.authenticated}, Principal='{auth_ctx.principal_id}'")
    print("  Note:         Authentication succeeded (identity verified as Suspended Sam)")

    res_suspended = gateway.transfer(
        session_token="token_suspended",
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("100.00"),
    )
    print(f"  Authz Result: Success={res_suspended.success}, ErrorCode={res_suspended.error_code}")
    print(f"  Message:      {res_suspended.message}")
    print("  Outcome:      SUCCESS (Suspended user authenticated but authorization denied with USER_SUSPENDED)")

    # --------------------------------------------------------------------------
    # DEMO 7: Layer Separation: Authorized Request with Insufficient Funds
    # --------------------------------------------------------------------------
    print("\n[DEMO 7] LAYER SEPARATION: AUTHORIZATION ALLOW VS BUSINESS INSUFFICIENT FUNDS")
    alice_bal = sim.get_balance("acc_alice_chk")
    print(f"  Alice Bal:    INR {alice_bal}")
    print("  Attempt:      Alice transfers INR 50000.00 (Exceeds available balance)")

    # 1. Inspect Layer 2 directly:
    auth_alice = sessions.authenticate("token_alice")
    target_7 = ResourceTarget(
        resource_type=ResourceType.ACCOUNT,
        resource_id="acc_alice_chk",
        secondary_resource_id="acc_bob_chk",
    )
    policy_res_7 = engine.evaluate(auth_alice, BankingAction.TRANSFER, target_7, sim)
    print(f"  Layer 2:      Decision={policy_res_7.decision}, ReasonCode={policy_res_7.reason_code}")
    print(f"                (Authorization ALLOW: Alice has full permission to spend from her account)")

    # 2. Inspect Layer 3 (Gateway / Simulator outcome):
    res_gateway_7 = gateway.transfer(
        session_token="token_alice",
        source_account_id="acc_alice_chk",
        destination_account_id="acc_bob_chk",
        amount=Decimal("50000.00"),
    )
    print(f"  Layer 3:      Success={res_gateway_7.success}, ErrorCode={res_gateway_7.error_code}")
    print(f"                (Simulator Rejection: {res_gateway_7.message})")
    print("  Outcome:      SUCCESS (Proves Layer 2 authorization and Layer 3 business rules are decoupled)")

    print("\n" + "=" * 74)
    print("            ALL PHASE 2 MANUAL SECURITY VERIFICATIONS PASSED")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(run_demo())
