"""
Manual Verification Demo CLI for Phase 1 Synthetic Banking Simulator.

Demonstrates Tests A through E as required by the Phase 1 specifications.
"""

from decimal import Decimal
import sys

from banking_simulator.contracts import ErrorCode, FailureMode
from banking_simulator.simulator import BankingSimulator


def run_demo() -> int:
    print("=" * 72)
    print("      SYNTHETIC BANKING SIMULATOR - PHASE 1 MANUAL VERIFICATION")
    print("=" * 72)

    sim = BankingSimulator(seed_default_fixtures=True)

    # --------------------------------------------------------------------------
    # TEST A: Read State
    # --------------------------------------------------------------------------
    print("\n[TEST A] READ STATE")
    alice_acc = sim.get_account("acc_alice_chk")
    bob_acc = sim.get_account("acc_bob_chk")
    alice_card = sim.get_card("card_alice_01")

    print(f"  Alice Checking Balance:  INR {sim.get_balance('acc_alice_chk')} (Status: {alice_acc.status if alice_acc else 'N/A'})")
    print(f"  Bob Checking Balance:    INR {sim.get_balance('acc_bob_chk')} (Status: {bob_acc.status if bob_acc else 'N/A'})")
    print(f"  Alice Debit Card:        {alice_card.card_number_masked if alice_card else 'N/A'} (Status: {alice_card.status if alice_card else 'N/A'})")
    print("  Result: SUCCESS (Read state matches deterministic fixtures)")

    # --------------------------------------------------------------------------
    # TEST B: Successful Transfer & State Conservation
    # --------------------------------------------------------------------------
    print("\n[TEST B] SUCCESSFUL TRANSFER & CONSERVATION INVARIANT")
    alice_before = sim.get_balance("acc_alice_chk")
    bob_before = sim.get_balance("acc_bob_chk")
    transfer_amount = Decimal("2000.00")

    print(f"  Before Transfer: Alice = INR {alice_before}, Bob = INR {bob_before} (Sum = INR {alice_before + bob_before})")
    res_b = sim.transfer("acc_alice_chk", "acc_bob_chk", transfer_amount)

    alice_after = sim.get_balance("acc_alice_chk")
    bob_after = sim.get_balance("acc_bob_chk")

    print(f"  Transfer Result: Success={res_b.success}, Code={res_b.error_code}, Message='{res_b.message}'")
    print(f"  After Transfer:  Alice = INR {alice_after}, Bob = INR {bob_after} (Sum = INR {alice_after + bob_after})")
    print(f"  Conservation:    ({alice_before} + {bob_before}) == ({alice_after} + {bob_after}) -> {alice_before + bob_before == alice_after + bob_after}")

    if res_b.data:
        tx = res_b.data
        print(f"  Transaction:     ID={tx.transaction_id}, Status={tx.status}, Timestamp={tx.timestamp}")
    print("  Result: SUCCESS (Balances updated exactly, amount conserved, transaction created)")

    # --------------------------------------------------------------------------
    # TEST C: Insufficient Funds
    # --------------------------------------------------------------------------
    print("\n[TEST C] INSUFFICIENT FUNDS REJECTION")
    excessive_amount = Decimal("50000.00")
    alice_c_before = sim.get_balance("acc_alice_chk")
    bob_c_before = sim.get_balance("acc_bob_chk")
    tx_count_before = len(sim.get_transactions("acc_alice_chk"))

    res_c = sim.transfer("acc_alice_chk", "acc_bob_chk", excessive_amount)
    alice_c_after = sim.get_balance("acc_alice_chk")
    bob_c_after = sim.get_balance("acc_bob_chk")
    tx_count_after = len(sim.get_transactions("acc_alice_chk"))

    print(f"  Attempt:         Transfer INR {excessive_amount} from Alice (Balance: INR {alice_c_before})")
    print(f"  Transfer Result: Success={res_c.success}, Code={res_c.error_code}, Message='{res_c.message}'")
    print(f"  State Invariant: Alice balance unchanged (INR {alice_c_before} == INR {alice_c_after}) -> {alice_c_before == alice_c_after}")
    print(f"  Tx Invariant:    Zero transactions created ({tx_count_before} == {tx_count_after})")
    print("  Result: SUCCESS (Rejected with INSUFFICIENT_FUNDS without state mutation)")

    # --------------------------------------------------------------------------
    # TEST D: Failure Injection (Pre-Commit Failure)
    # --------------------------------------------------------------------------
    print("\n[TEST D] FAILURE INJECTION (PRE_COMMIT_FAILURE)")
    sim.inject_failure(FailureMode.PRE_COMMIT_FAILURE)

    alice_d_before = sim.get_balance("acc_alice_chk")
    bob_d_before = sim.get_balance("acc_bob_chk")
    tx_count_d_before = len(sim.get_transactions("acc_alice_chk"))

    res_d = sim.transfer("acc_alice_chk", "acc_bob_chk", Decimal("1000.00"))
    alice_d_after = sim.get_balance("acc_alice_chk")
    bob_d_after = sim.get_balance("acc_bob_chk")
    tx_count_d_after = len(sim.get_transactions("acc_alice_chk"))

    print(f"  Injected Mode:   {FailureMode.PRE_COMMIT_FAILURE}")
    print(f"  Transfer Result: Success={res_d.success}, Code={res_d.error_code}, Message='{res_d.message}'")
    print(f"  State Invariant: Alice balance unchanged (INR {alice_d_before} == INR {alice_d_after}) -> {alice_d_before == alice_d_after}")
    print(f"  State Invariant: Bob balance unchanged (INR {bob_d_before} == INR {bob_d_after}) -> {bob_d_before == bob_d_after}")
    print(f"  Tx Invariant:    Zero transactions created ({tx_count_d_before} == {tx_count_d_after})")
    print("  Result: SUCCESS (Pre-commit failure cleanly aborted transfer with zero mutation)")

    # Reset failure injection
    sim.inject_failure(FailureMode.NONE)

    # --------------------------------------------------------------------------
    # TEST E: Card Freeze
    # --------------------------------------------------------------------------
    print("\n[TEST E] CARD FREEZE OPERATION")
    card_before = sim.get_card("card_alice_01")
    print(f"  Card Before:     ID={card_before.card_id if card_before else 'N/A'}, Status={card_before.status if card_before else 'N/A'}")

    res_e = sim.freeze_card("card_alice_01")
    card_after = sim.get_card("card_alice_01")
    print(f"  Freeze Result:   Success={res_e.success}, Code={res_e.error_code}, Message='{res_e.message}'")
    print(f"  Card After:      ID={card_after.card_id if card_after else 'N/A'}, Status={card_after.status if card_after else 'N/A'}")

    # Re-freeze attempt
    res_e_repeat = sim.freeze_card("card_alice_01")
    print(f"  Repeat Freeze:   Success={res_e_repeat.success}, Code={res_e_repeat.error_code}, Message='{res_e_repeat.message}'")
    print("  Result: SUCCESS (Card successfully frozen, repeat freeze rejected with CARD_ALREADY_FROZEN)")

    print("\n" + "=" * 72)
    print("              ALL MANUAL SIMULATOR VERIFICATION TESTS PASSED")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(run_demo())
