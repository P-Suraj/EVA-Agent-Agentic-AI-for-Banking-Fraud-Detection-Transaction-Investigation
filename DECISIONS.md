# Architecture Decision Records (ADRs)

## ADR-001: Exact Decimal Arithmetic for Monetary Balances
- **Status**: `VERIFIED`
- **Context**: Financial calculations cannot tolerate IEEE-754 floating-point inaccuracies (e.g., `0.1 + 0.2 != 0.3`).
- **Decision**: All balances, transfer amounts, and financial validations strictly use Python's `decimal.Decimal` quantized to two decimal places (`0.01`). Float inputs are rejected with `ErrorCode.INVALID_AMOUNT`.
- **Alternatives Considered**:
  - `float`: Rejected due to non-deterministic rounding errors.
  - Integer minor units (cents/paise): Viable, but `Decimal` provides cleaner API representations for simulated reporting while guaranteeing exact arithmetic.

---

## ADR-002: Isolated In-Memory State Without Shared Globals
- **Status**: `VERIFIED`
- **Context**: Multi-scenario evaluation and parallel automated testing require independent, repeatable state.
- **Decision**: Every `BankingSimulator()` instance creates its own dictionary stores (`_users`, `_accounts`, `_beneficiaries`, `_cards`, `_transactions`, `_idempotency_store`). No module-level mutable state exists.
- **Alternatives Considered**:
  - Global singleton: Rejected because tests would cross-contaminate state.
  - SQLite/In-memory database: Rejected for Phase 1 to avoid unnecessary database dependencies and connection overhead.

---

## ADR-003: Deterministic Simulated Clock
- **Status**: `VERIFIED`
- **Context**: Using system `datetime.now()` produces non-deterministic timestamps across runs, breaking reproducibility in regression tracking.
- **Decision**: Implemented `SimulatedClock` initialized at `"2026-01-01T12:00:00Z"`. All transaction timestamps originate from this clock, advancing deterministically.
- **Alternatives Considered**:
  - System `datetime.now()`: Rejected due to test non-determinism.
  - Mocking `datetime` globally via `unittest.mock`: Rejected as fragile and prone to test runner interference.

---

## ADR-004: Deterministic Transaction Identifiers
- **Status**: `VERIFIED`
- **Context**: UUIDs introduce random string variance across identical test runs.
- **Decision**: Transactions are identified using an instance-local monotonic counter formatted as `tx_{counter:04d}` (e.g. `tx_0001`, `tx_0002`).
- **Alternatives Considered**:
  - `uuid.uuid4()`: Rejected due to non-reproducibility across runs.

---

## ADR-005: Deterministic Error Codes & Public Contract Boundary
- **Status**: `VERIFIED`
- **Context**: Uncaught Pydantic `ValidationError` exceptions leaking from banking operations break programmatic callers and evaluation runners.
- **Decision**: Public operations return `OperationResult[T]` containing typed `ErrorCode` values. An explicit 11-step validation ordering is enforced:
  1. Idempotency $\rightarrow$ 2. Amount $\rightarrow$ 3. Source Existence $\rightarrow$ 4. Dest Existence $\rightarrow$ 5. Beneficiary checks $\rightarrow$ 6. Source Status $\rightarrow$ 7. Dest Status $\rightarrow$ 8. Currency $\rightarrow$ 9. Balance $\rightarrow$ 10. Pre-Commit Failure $\rightarrow$ 11. Commit.
- **Alternatives Considered**:
  - Raising Python exceptions: Rejected for business logic failures; exceptions are reserved for unexpected programming bugs.

---

## ADR-006: Explicit Beneficiary Ownership Contract
- **Status**: `VERIFIED`
- **Context**: A beneficiary belongs to an owner user. Transacting without ownership parameters causes ambiguity.
- **Decision**: `transfer_to_beneficiary` requires `owner_user_id`. The simulator verifies that `beneficiary.owner_user_id == owner_user_id` and `status == VERIFIED`, returning `BENEFICIARY_OWNERSHIP_MISMATCH` or `BENEFICIARY_NOT_VERIFIED` on mismatch.
- **Boundary**: Real authorization policy (e.g., OPA/RBAC) is explicitly deferred to Phase 2; the simulator only performs model-level consistency checks.

---

## ADR-007: Deferral of Dispute Workflows and Deposit Operations
- **Status**: `VERIFIED`
- **Context**: Pre-emptively building dispute state machines or deposit intake introduces speculative complexity without immediate Phase 1 test requirements.
- **Decision**: Marked dispute workflows and deposit operations as `DEFERRED`. The `TransactionType` enum contains only `TRANSFER`. `TransactionStatus` defines `POSTED` (active) and `FAILED` (reserved for future phases; no failed transactions are persisted in Phase 1).
- **Alternatives Considered**:
  - Implementing minimal dispute stub: Rejected to maintain strict scope control and avoid unused code.

---

## ADR-008: Deterministic Pure-Python Policy Engine (Deferring OPA)
- **Status**: `VERIFIED`
- **Context**: Evaluating authorization rules could be done via an embedded Open Policy Agent (OPA) server / Rego daemon or a pure-Python deterministic policy engine.
- **Decision**: Implemented `DeterministicPolicyEngine` in pure Python. The engine takes `(AuthContext, Action, ResourceTarget, SimulatorState)` and returns machine-readable `PolicyResult` (`ALLOW` / `DENY`) with deterministic `PolicyReasonCode`. External OPA integration is explicitly `DEFERRED`.
- **Alternatives Considered**:
  - OPA (Open Policy Agent) daemon: Rejected for Phase 2 because it introduces an external daemon binary, network IPC latency, and excessive complexity for deterministic in-memory rule sets. Pure Python keeps evaluation zero-dependency, sub-millisecond, and fully reproducible.

---

## ADR-009: Simulated Session Credential Trust Boundary & Identity Immutability
- **Status**: `VERIFIED`
- **Context**: Future agent components must not be able to forge or elevate caller identities (e.g. passing arbitrary `principal_id` or setting `authenticated=True`).
- **Decision**: Callers supply only opaque simulated session token strings (e.g. `"token_alice"`). The `SimulatedSessionManager` resolves tokens into frozen, immutable `AuthContext` objects (`extra="forbid"`, `frozen=True`). Session provisioning (`provision_session`) is strictly a trusted test/fixture setup operation, not exposed to gateway callers or future agents.
- **Alternatives Considered**:
  - Passing `principal_id` in request payloads: Rejected as highly vulnerable to confused-deputy and identity-spoofing attacks.
  - Real JWT / cryptographic tokens: Rejected as out-of-scope for the simulated testbed; session tokens are deterministic simulated credentials for test environments.

---

## ADR-010: Direct Transfer Authorization Semantics (Source Ownership vs Destination Target)
- **Status**: `VERIFIED`
- **Context**: Peer-to-peer transfers involve a source account and a destination account. A sender obviously does not own the recipient's account.
- **Decision**: Authorization for `TRANSFER_DIRECT` checks that the caller owns the *source* account. The destination account is treated as a transaction target parameter, not an owned authorization resource. Destination account validity (active status, currency match) is independently verified by Layer 3 (the simulator) business rules.
- **Alternatives Considered**:
  - Requiring sender to own both accounts: Rejected because peer-to-peer transfers to other users would be impossible.
  - Omitting source ownership checks: Rejected because callers could drain other users' funds (confused-deputy).

---

## ADR-011: Gateway Facade Pattern for Pre-Execution Policy Enforcement
- **Status**: `VERIFIED`
- **Context**: If authorization checks and simulator execution are called ad-hoc by callers, callers could accidentally bypass security checks and mutate state directly.
- **Decision**: Implemented `SecureBankingGateway` as the authoritative single entry point. The gateway validates session tokens via `SimulatedSessionManager`, queries `DeterministicPolicyEngine`, and only invokes the underlying `BankingSimulator` if the decision is `ALLOW`. Unauthorized requests fail-closed with `PERMISSION_DENIED` before any simulator method is invoked.
- **Alternatives Considered**:
  - Decorator-based enforcement: Rejected because decorators obscure execution flow and can be accidentally omitted on newly added methods.
  - Embedding security checks directly inside `BankingSimulator`: Rejected to maintain strict architectural layer separation between financial state machine (Layer 3) and security policy (Layer 2).

---

## ADR-012: Transaction Request Immutability & Rejection of Silent Precision Rounding
- **Status**: `VERIFIED`
- **Context**: LLM agents may hallucinate sub-cent precision (e.g. `100.123`) or submit uncanonicalized Decimal values (e.g. `100.1`). Silently rounding amounts can conceal fraud or hallucinated amounts.
- **Decision**: Implemented `TransactionRequest` as a sealed, frozen Pydantic model (`frozen=True`, `extra="forbid"`). Amounts with $>2$ decimal places are strictly rejected with `INVALID_TRANSACTION_REQUEST`. Silent rounding or parameter modification is forbidden. Lossless canonical representation (`100.1` and `100.10` $\rightarrow$ `"100.10"`) is used for deterministic SHA-256 fingerprinting. Every state-changing request requires a mandatory non-empty `idempotency_key`.
- **Alternatives Considered**:
  - Silently quantizing to 2 decimal places: Rejected because silent parameter alteration violates the deterministic safety boundary.
  - Optional idempotency keys: Rejected because financial transaction execution without idempotency invites replay exploits.

---

## ADR-013: Deterministic Limits & Public SimulatedClock Dependency Injection
- **Status**: `VERIFIED`
- **Context**: Evaluating per-transaction limits, UTC calendar day cumulative caps, and velocity rolling windows requires access to current time. Accessing private attributes (such as `simulator._clock` or `_current_time`) violates encapsulation and creates fragile layer couplings.
- **Decision**: `TransactionLimitEvaluator` and `SecureExecutionGateway` take `SimulatedClock` via constructor dependency injection. All time computations strictly invoke the public API `clock.now_iso()`, parsing timestamps via Python's standard `datetime.fromisoformat()`. Zero private clock or simulator internals are accessed.
- **Alternatives Considered**:
  - Accessing `simulator._clock`: Rejected to preserve encapsulation of Phase 1.
  - Calling system `datetime.now()`: Rejected as it introduces non-determinism into test suites.

---

## ADR-014: Trusted Step-Up Approval Trust Boundary & Non-Burn Failure Semantics
- **Status**: `VERIFIED`
- **Context**: High-risk transactions (amount $\ge$ threshold) require elevated verification. Callers/agents must not be able to self-assert approval or fabricate approval objects. Furthermore, if a transaction is approved but the simulator rejects it due to business policy (e.g. `INSUFFICIENT_FUNDS`), consuming the approval prematurely forces the user to repeat unnecessary approvals.
- **Decision**: Implemented `SimulatedStepUpApprovalService` as an authoritative provider. Approvals are cryptographically simulated, sealed as `StepUpApproval`, and registered internally. Approval follows the exact lifecycle: `verify → execute → consume only after successful POSTED execution`. Known simulator failures preserve the approval token so the caller can retry after funding the account.
- **Alternatives Considered**:
  - Consuming approval on verification: Rejected because a subsequent simulator balance rejection would burn the valid approval.
  - Passing `approved=True` in payload: Rejected as trivial to bypass for an untrusted caller.

---

## ADR-015: Tenant-Scoped Authoritative Idempotency & At-Most-Once Execution
- **Status**: `VERIFIED`
- **Context**: Multi-tenant banking systems require clients to submit idempotency keys. If idempotency keys are globally scoped, two clients using `"req-001"` will collide across tenants.
- **Decision**: Implemented `AuthoritativeIdempotencyStore` keyed by `(principal_id, idempotency_key)`. Replaying an identical transaction returns the cached result without invoking the simulator (mutation count = 0). Conflicting parameters return `IDEMPOTENCY_CONFLICT`. To prevent cross-tenant collisions in the underlying simulator's internal store, the gateway passes `scoped_idempotency_key = f"{principal_id}:{request.idempotency_key}"` to simulator transfer methods.
- **Boundary**: Guarantees at-most-once execution within the single-process simulated boundary; explicitly does not claim distributed exactly-once execution.
