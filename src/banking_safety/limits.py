"""
Deterministic Transaction Limit Evaluator for Banking Safety.

Evaluates per-transaction, daily cumulative, velocity limits, and currency restrictions
using ONLY the public SimulatedClock API.
Zero access to private clock or simulator internals.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from banking_safety.config import TransactionSafetyConfig
from banking_safety.contracts import SafetyDecision, SafetyReasonCode, SafetyResult
from banking_safety.request import TransactionRequest
from banking_simulator.clock import SimulatedClock
from banking_simulator.models import TransactionStatus
from banking_simulator.simulator import BankingSimulator


class TransactionLimitEvaluator:
    """
    Evaluates financial limits against simulator state and deterministic simulated time.
    """

    def __init__(self, clock: Optional[SimulatedClock] = None):
        self._clock = clock or SimulatedClock()

    @property
    def clock(self) -> SimulatedClock:
        """Public reference to the deterministic clock."""
        return self._clock

    def evaluate_limits(
        self,
        request: TransactionRequest,
        simulator: BankingSimulator,
        config: TransactionSafetyConfig,
    ) -> SafetyResult:
        """
        Evaluate currency match, per-transaction limit, daily cumulative limit,
        and velocity count against public simulator history.
        """
        now_iso = self._clock.now_iso()
        now_dt = datetime.fromisoformat(now_iso)
        current_utc_date = now_iso[:10]  # "YYYY-MM-DD"
        fingerprint = request.compute_fingerprint()

        # ----------------------------------------------------------------------
        # 1. Currency Match Check (Fail Closed before any state evaluation)
        # ----------------------------------------------------------------------
        if request.currency != config.currency:
            return SafetyResult(
                decision=SafetyDecision.DENY,
                reason_code=SafetyReasonCode.CURRENCY_UNSUPPORTED,
                message=(
                    f"Currency '{request.currency}' is unsupported. "
                    f"Configured currency is '{config.currency}' (conversion prohibited)."
                ),
                fingerprint=fingerprint,
                evaluated_at=now_iso,
                metadata={"requested_currency": request.currency, "enforced_currency": config.currency},
            )

        # ----------------------------------------------------------------------
        # 2. Per-Transaction Limit Check
        # ----------------------------------------------------------------------
        if request.amount > config.per_transaction_limit:
            return SafetyResult(
                decision=SafetyDecision.DENY,
                reason_code=SafetyReasonCode.PER_TRANSACTION_LIMIT_EXCEEDED,
                message=(
                    f"Transfer amount {request.amount} {request.currency} exceeds "
                    f"per-transaction limit of {config.per_transaction_limit} {config.currency}."
                ),
                fingerprint=fingerprint,
                evaluated_at=now_iso,
                metadata={
                    "requested_amount": str(request.amount),
                    "per_transaction_limit": str(config.per_transaction_limit),
                },
            )

        # ----------------------------------------------------------------------
        # Query Public Transaction History for Outbound Account
        # ----------------------------------------------------------------------
        account_transactions = simulator.get_transactions(request.source_account_id)

        # ----------------------------------------------------------------------
        # 3. Daily Cumulative Transfer Limit Check
        # ----------------------------------------------------------------------
        # Only POSTED outbound transactions on the current UTC calendar day count
        daily_posted_sum = Decimal("0.00")
        for tx in account_transactions:
            if tx.source_account_id == request.source_account_id and tx.status == TransactionStatus.POSTED:
                if tx.timestamp[:10] == current_utc_date:
                    daily_posted_sum += tx.amount

        if daily_posted_sum + request.amount > config.daily_transfer_limit:
            return SafetyResult(
                decision=SafetyDecision.DENY,
                reason_code=SafetyReasonCode.DAILY_LIMIT_EXCEEDED,
                message=(
                    f"Daily cumulative limit exceeded for account '{request.source_account_id}': "
                    f"current daily sum {daily_posted_sum} + requested {request.amount} "
                    f"exceeds limit of {config.daily_transfer_limit} {config.currency} on {current_utc_date}."
                ),
                fingerprint=fingerprint,
                evaluated_at=now_iso,
                metadata={
                    "daily_posted_sum": str(daily_posted_sum),
                    "requested_amount": str(request.amount),
                    "daily_transfer_limit": str(config.daily_transfer_limit),
                    "date": current_utc_date,
                },
            )

        # ----------------------------------------------------------------------
        # 4. Deterministic Velocity Rule Check
        # ----------------------------------------------------------------------
        # Rolling time window: [now_dt - window_seconds, now_dt]
        window_start_dt = now_dt - timedelta(seconds=config.velocity_window_seconds)
        qualifying_outbound_count = 0

        for tx in account_transactions:
            if tx.source_account_id == request.source_account_id and tx.status == TransactionStatus.POSTED:
                tx_dt = datetime.fromisoformat(tx.timestamp)
                if window_start_dt <= tx_dt <= now_dt:
                    qualifying_outbound_count += 1

        if qualifying_outbound_count >= config.velocity_count_limit:
            return SafetyResult(
                decision=SafetyDecision.DENY,
                reason_code=SafetyReasonCode.VELOCITY_LIMIT_EXCEEDED,
                message=(
                    f"Velocity limit exceeded for account '{request.source_account_id}': "
                    f"{qualifying_outbound_count} outbound transfers in the past "
                    f"{config.velocity_window_seconds}s (limit is {config.velocity_count_limit})."
                ),
                fingerprint=fingerprint,
                evaluated_at=now_iso,
                metadata={
                    "qualifying_count": qualifying_outbound_count,
                    "velocity_limit": config.velocity_count_limit,
                    "window_seconds": config.velocity_window_seconds,
                },
            )

        # All limit evaluations passed cleanly
        return SafetyResult(
            decision=SafetyDecision.ALLOW,
            reason_code=SafetyReasonCode.SAFETY_ALLOWED,
            message="Transaction parameters are within configured limits.",
            fingerprint=fingerprint,
            evaluated_at=now_iso,
            metadata={
                "daily_posted_sum": str(daily_posted_sum),
                "velocity_count": qualifying_outbound_count,
            },
        )
