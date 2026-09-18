# Changelog

All notable changes to the Secure Agentic Banking Assistant project are documented in this file.

## [Phase 3: Transaction Safety & Deterministic Execution Gate] - 2026-09-15

### Added
- **`src/banking_safety/` Package**:
  - `contracts.py`: Implemented deterministic enums `SafetyDecision` (`ALLOW`, `DENY`, `STEP_UP_REQUIRED`), `SafetyReasonCode` (7 distinct reason codes), `GateStage` (`AUTHENTICATION`, `AUTHORIZATION`, `TRANSACTION_SAFETY`, `SIMULATOR_EXECUTION`, `IDEMPOTENCY_REPLAY`), and Pydantic models `SafetyResult` and `ExecutionGateResult`.
  - `request.py`: Implemented `TransactionRequest` (frozen Pydantic model, `extra="forbid"`) enforcing mandatory non-empty `idempotency_key`, strict Decimal validation (rejecting floats and amounts with $>2$ decimal places without silent rounding), canonical formatting `canonical_amount_str`, mutually exclusive destination targets (`destination_account_id` vs. `beneficiary_id`), and deterministic SHA-256 `compute_fingerprint()`.
  - `config.py`: Implemented immutable `TransactionSafetyConfig` defining per-transaction limits (INR 25,000.00), daily cumulative limits (INR 50,000.00), rolling velocity limits (3 transfers / 3600s), step-up thresholds (INR 5,000.00), approval TTL (300s), and currency whitelist ("INR").
  - `limits.py`: Implemented `TransactionLimitEvaluator` checking currency conformance, per-transaction ceiling, daily cumulative ceiling on UTC calendar days (`SimulatedClock.now_iso()[:10]`), and rolling outbound transfer count within a configured time window.
  - `idempotency.py`: Implemented `AuthoritativeIdempotencyStore` scoped strictly by `(principal_id, idempotency_key)` guaranteeing single-process at-most-once semantics; returns cached `ExecutionGateResult` on exact replay, detects and rejects payload conflicts, and ensures uncommitted/failed attempts do not consume the key.
  - `approval.py`: Implemented `StepUpApproval` (frozen, bound to `principal_id`, `transaction_fingerprint`, and expiry) and `SimulatedStepUpApprovalService` (issuing approvals, validating unconsumed tokens, and non-burn lifecycle preserving approvals on simulator rejections).
  - `engine.py`: Implemented `TransactionSafetyEngine` enforcing strict deterministic evaluation precedence (idempotency key presence -> cached replay short-circuit -> currency check -> per-tx limit -> daily limit -> velocity limit -> step-up approval verification).
  - `gateway.py`: Implemented `SecureExecutionGateway` orchestrating the 4-layer execution pipeline (Phase 2 Auth & Authz -> Phase 3 Safety -> Phase 1 Simulator -> Phase 3 Idempotency Commit & Approval Consumption); delegates read operations and card freeze, isolates multi-tenant idempotency keys via `scoped_idempotency_key = f"{principal_id}:{request.idempotency_key}"`, and guarantees zero simulator mutation on pre-execution denials.
  - `demo.py`: Implemented verification CLI demo covering 8 realistic financial safety scenarios.
- **Automated Tests (`tests/`)**:
  - Added 43 automated tests across 7 test suites:
    - `test_transaction_request.py` (11 tests): Validation of required idempotency keys, sub-cent precision rejection, decimal canonicalization, target mutual exclusivity, and fingerprint sensitivity.
    - `test_transaction_limits.py` (6 tests): Currency mismatch fail-closed, per-transaction limit, daily cumulative limit on UTC day, failed transfer non-counting, velocity windowing.
    - `test_transaction_idempotency.py` (6 tests): Cached replay without simulator call, conflict detection on amount/recipient, multi-tenant isolation, non-commitment on insufficient funds and pre-commit failure.
    - `test_transaction_approval.py` (8 tests): Threshold triggering, valid execution, amount/recipient tampering detection, single-use enforcement, expiration, untrusted token rejection, approval preservation on simulator rejection.
    - `test_transaction_safety_engine.py` (4 tests): Strict evaluation precedence and short-circuiting.
    - `test_transaction_execution_gate.py` (4 tests): End-to-end direct and beneficiary pipeline execution, simulator mutation zero count invariant, simulator failure isolation.
    - `test_transaction_security.py` (4 tests): Threat model verification (Wrong Amount = 0, Wrong Recipient = 0, Confused Deputy = 0, and metrics calculation suite).
- **Living Documentation**:
  - `CURRENT_PHASE.md`: Advanced to Phase 3 — Transaction Safety & Deterministic Execution Gate (Verified) with full verification checklist.
  - `ARCHITECTURE.md`: Documented 4-layer execution pipeline, component boundaries, and simulator bypass claims.
  - `DECISIONS.md`: Added ADR-012 (Authoritative In-Memory Idempotency), ADR-013 (Deterministic Step-Up Approval), ADR-014 (Rejecting Sub-Cent Precision), and ADR-015 (Strict Evaluation Precedence).
  - `TESTING.md`: Updated test inventory to 136 tests and documented manual verification outputs.

---

## [Phase 2: Authentication & Deterministic Authorization] - 2026-09-12

### Added
- **`src/banking_security/` Package**:
  - `context.py`: Implemented `AuthContext` (immutable, frozen Pydantic model with `extra="forbid"`) and `SimulatedSessionManager` (isolated credential resolution boundary).
  - `actions.py`: Added `BankingAction` StrEnum (`READ_ACCOUNT`, `READ_BALANCE`, `READ_TRANSACTIONS`, `TRANSFER_DIRECT`, `TRANSFER_BENEFICIARY`, `FREEZE_CARD`), `ResourceType` StrEnum, and `ResourceTarget`.
  - `contracts.py`: Added `PolicyDecision` (`ALLOW` / `DENY`), `PolicyReasonCode`, and `PolicyResult` models.
  - `engine.py`: Implemented `DeterministicPolicyEngine` enforcing fail-closed evaluation, decoupled suspended user checks (`USER_SUSPENDED`), ground-truth simulator ownership checks, direct transfer target semantics, and beneficiary verification rules.
  - `gateway.py`: Implemented `SecureBankingGateway` as an authorized facade gating all simulator access behind Layer 1 authentication and Layer 2 deterministic authorization.
  - `demo.py`: Implemented CLI verification demo exercising DEMO 1 through 7.
- **Automated Tests (`tests/`)**:
  - Added 31 automated tests across 5 test suites:
    - `test_security_auth.py` (6 tests): Valid/invalid tokens, context immutability, extra forbid, suspended user authentication.
    - `test_security_authorization.py` (14 tests): Read permissions, direct transfer permissions, beneficiary transfer verification, card freeze, suspended user denial, unknown entities, unauthenticated denial.
    - `test_security_confused_deputy.py` (3 tests): Source account impersonation, destination ownership non-privilege, caller claim bypass rejection.
    - `test_security_gateway.py` (5 tests): Gateway facade invocation, unauthorized access prevention, direct transfer dispatch.
    - `test_security_layer_separation.py` (3 tests): Non-corruption on denial, authorization ALLOW vs business INSUFFICIENT_FUNDS separation, frozen destination separation.
- **Simulator Contract Extension**:
  - Added `ErrorCode.PERMISSION_DENIED = "PERMISSION_DENIED"` to `src/banking_simulator/contracts.py`.
- **Living Documentation**:
  - `CURRENT_PHASE.md`: Advanced to Phase 2 Verified with complete capability breakdown and acceptance checklist.
  - `ARCHITECTURE.md`: Added 3-layer execution pipeline diagram and security component boundaries.
  - `DECISIONS.md`: Added ADR-008 through ADR-011 documenting security architecture decisions.
  - `TESTING.md`: Documented 93 automated tests and manual security demo execution.

---

## [Phase 1: Synthetic Banking Simulator] - 2026-09-12

### Added
- **`src/banking_simulator/` Package**:
  - `clock.py`: Implemented `SimulatedClock` starting at epoch `"2026-01-01T12:00:00Z"` with deterministic ISO-8601 formatting.
  - `models.py`: Added typed Pydantic domain entities (`User`, `Account`, `Beneficiary`, `Transaction`, `Card`) enforcing exact `Decimal` arithmetic for monetary fields.
  - `contracts.py`: Added `OperationResult[T]`, `ErrorCode` StrEnum, and `FailureMode` StrEnum.
  - `fixtures.py`: Added isolated deterministic seed data factories for default users, accounts, beneficiaries, and cards.
  - `simulator.py`: Implemented `BankingSimulator` core state machine with read operations, account transfer, beneficiary transfer, card freeze, 11-step error precedence, pre-commit failure injection, and in-memory idempotency cache.
  - `demo.py`: Created CLI manual verification demo implementing Tests A–E.
- **Automated Tests (`tests/`)**:
  - Added 27 automated tests across 6 test modules:
    - `test_simulator_models.py` (8 tests)
    - `test_simulator_reads.py` (4 tests)
    - `test_simulator_transfers.py` (8 tests)
    - `test_simulator_cards.py` (3 tests)
    - `test_simulator_failure_injection.py` (1 test)
    - `test_simulator_idempotency.py` (3 tests)
- **Living Documentation**:
  - `ARCHITECTURE.md`: Living architecture specification and boundaries.
  - `DECISIONS.md`: ADR-001 through ADR-007 documenting key design decisions and rationale.
  - `TESTING.md`: Complete test inventory and verified execution logs.
  - `CHANGELOG.md`: Chronological change history.

### Changed
- `CURRENT_PHASE.md`: Advanced status to Phase 1 — Synthetic Banking Simulator (Verified).
- `README.md`: Documented simulator usage, architecture, and verification instructions.

### Deferred
- Transaction dispute workflow (`dispute_transaction`) deferred to later phases.
- Deposit operations (`DEPOSIT` transaction type) deferred to later phases.
- Authorization policy engine (OPA / RBAC) deferred to Phase 2.

---

## [Phase 0: Evaluation Foundation] - 2026-09-11

### Added
- Initial project skeleton with Git hygiene (`.gitignore`, `pyproject.toml`).
- `banking_eval` package:
  - `schema.py`: Canonical evaluation schema (`EvaluationCase`, `PredictionResult`, `CaseEvaluationResult`).
  - `adapter.py`: Abstract `DatasetAdapter` and concrete `SyntheticBankingIntentAdapter`.
  - `baseline.py`: Transparent rule/keyword-based intent classifier.
  - `metrics.py`: Pure-Python Accuracy, per-intent metrics, and Macro-F1.
  - `runner.py`: Evaluation runner with independent framework safety-veto logic.
  - `reporting.py`: Formatted terminal reporting and machine-readable JSON output.
- `datasets/synthetic_banking_intents.json`: 12 documented test cases.
- 35 automated pytest tests (`tests/test_schema.py`, `tests/test_adapter.py`, `tests/test_baseline.py`, `tests/test_metrics.py`, `tests/test_runner.py`, `tests/test_safety_veto.py`).
- Phase 0 documentation in `README.md` and `CURRENT_PHASE.md`.
