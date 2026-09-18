"""
Authoritative Idempotency Store for Transaction Safety.

Scoped by (principal_id, idempotency_key) to isolate retry namespaces.
Guarantees at-most-once execution within the single-process simulated boundary.
"""

from typing import Any, Optional

from banking_safety.contracts import ExecutionGateResult, SafetyReasonCode


class AuthoritativeIdempotencyStore:
    """
    In-memory authoritative idempotency store for the secure execution gateway.
    Stores successfully executed (POSTED) transaction outcomes.
    """

    def __init__(self):
        # Maps (principal_id, idempotency_key) -> (fingerprint, cached_ExecutionGateResult)
        self._store: dict[tuple[str, str], tuple[str, ExecutionGateResult[Any]]] = {}

    def check(
        self,
        principal_id: str,
        idempotency_key: str,
        fingerprint: str,
    ) -> tuple[Optional[ExecutionGateResult[Any]], Optional[SafetyReasonCode]]:
        """
        Check whether an idempotency key has been used by this principal.

        Returns:
            (cached_result, IDEMPOTENCY_REPLAY) if key and fingerprint match.
            (None, IDEMPOTENCY_CONFLICT) if key exists with different fingerprint.
            (None, None) if key has not been recorded (fresh execution permitted).
        """
        lookup_key = (principal_id, idempotency_key)
        if lookup_key not in self._store:
            return None, None

        stored_fp, cached_result = self._store[lookup_key]
        if stored_fp == fingerprint:
            return cached_result, SafetyReasonCode.IDEMPOTENCY_REPLAY
        else:
            return None, SafetyReasonCode.IDEMPOTENCY_CONFLICT

    def commit(
        self,
        principal_id: str,
        idempotency_key: str,
        fingerprint: str,
        result: ExecutionGateResult[Any],
    ) -> None:
        """
        Record a successfully committed (POSTED) transaction in the idempotency store.
        Must only be called after state mutation has committed in the simulator.
        """
        lookup_key = (principal_id, idempotency_key)
        self._store[lookup_key] = (fingerprint, result)

    def clear(self) -> None:
        """Clear store for test isolation."""
        self._store.clear()
