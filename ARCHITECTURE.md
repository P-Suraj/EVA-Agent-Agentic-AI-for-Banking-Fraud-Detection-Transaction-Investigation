# System Architecture

## Architectural Principle
> *"LLMs reason; deterministic systems enforce."*

The architecture enforces strict structural separation across independent, deterministic layers. Security, policy, and safety boundaries precede any future generative reasoning components.

---

## Component Boundaries

```
src/
├── banking_eval/            [Phase 0: Evaluation Foundation - FROZEN]
│   ├── schema.py            - Canonical typed evaluation test case models
│   ├── adapter.py           - Deterministic dataset conversion interface
│   ├── baseline.py          - Deterministic keyword rule baseline
│   ├── metrics.py           - Pure-Python Accuracy and Macro-F1 calculations
│   ├── runner.py            - Evaluation runner with independent safety-veto logic
│   └── reporting.py         - Human-readable CLI and JSON report generator
│
├── banking_simulator/       [Phase 1: Synthetic Banking Simulator - FROZEN]
│   ├── clock.py             - Deterministic SimulatedClock (zero datetime.now calls)
│   ├── models.py            - Domain models (User, Account, Beneficiary, Transaction, Card)
│   ├── contracts.py         - OperationResult[T], ErrorCode, FailureMode
│   ├── fixtures.py          - Deterministic seed state factories
│   ├── simulator.py         - In-memory state machine (transfers, card freeze, failure injection)
│   └── demo.py              - CLI verification suite (Tests A-E)
│
├── banking_security/        [Phase 2: Authentication & Deterministic Authorization - FROZEN]
│   ├── context.py           - AuthContext (immutable) & SimulatedSessionManager
│   ├── actions.py           - BankingAction StrEnum, ResourceTarget, ResourceType
│   ├── contracts.py         - PolicyDecision, PolicyReasonCode, PolicyResult
│   ├── engine.py            - DeterministicPolicyEngine (rule evaluation)
│   ├── gateway.py           - SecureBankingGateway (authorized simulator facade)
│   └── demo.py              - Security verification CLI demo (DEMO 1-7)
│
└── banking_safety/          [Phase 3: Transaction Safety & Deterministic Execution Gate - VERIFIED]
    ├── contracts.py         - SafetyDecision, SafetyReasonCode, SafetyResult, ExecutionGateResult
    ├── request.py           - TransactionRequest (strict validation, mandatory key, canonical fingerprint)
    ├── config.py            - TransactionSafetyConfig (immutable limit and threshold values)
    ├── limits.py            - TransactionLimitEvaluator (public clock API, per-tx, daily, velocity)
    ├── idempotency.py       - AuthoritativeIdempotencyStore (scoped to principal_id + key)
    ├── approval.py          # StepUpApproval & SimulatedStepUpApprovalService (verify -> execute -> consume)
    ├── engine.py            - TransactionSafetyEngine (orchestrates rules in deterministic order)
    ├── gateway.py           - SecureExecutionGateway (authorized & safety-gated execution facade)
    └── demo.py              - CLI manual verification demo (DEMO 1-8)
```

---

## Layered Execution Flow

Every state-changing transaction processed through the secure gateway follows a strict four-layer pipeline:

```
[Caller / Future Agent]
       ↓ (Provides session_token, TransactionRequest, optional StepUpApproval)
[Layer 1: Authentication Boundary (SimulatedSessionManager)]
Question: "Who is the caller?"
- Resolves opaque session token into immutable AuthContext.
- Fail-Closed: Unauthenticated or invalid token evaluates to DENY.
- Invariant: Simulator mutation invocation count = 0.

       ↓ (Authenticated AuthContext)
[Layer 2: Deterministic Authorization Engine (DeterministicPolicyEngine)]
Question: "Is this authenticated principal permitted to perform this operation?"
- Checks caller standing (SUSPENDED -> DENY).
- Checks resource ownership against ground-truth simulator state.
- For direct transfers, sender must own source account; destination is a target.
- For beneficiary transfers, sender must own source account, own beneficiary, and beneficiary must be VERIFIED.
- Fail-Closed: Unauthorized requests evaluate to DENY (PERMISSION_DENIED).
- Invariant: Simulator mutation invocation count = 0; safety limits unconsumed.

       ↓ (Authorized Request)
[Layer 3: Transaction Safety & Deterministic Gate (TransactionSafetyEngine)]
Question: "Given authorization, is this specific transaction safe, within limits, and approved?"
- Mandatory Idempotency: Missing or whitespace key fails closed.
- Replay Short-Circuit: Same (principal, key) + same fingerprint returns cached result without re-evaluating limits.
- Conflict Protection: Same (principal, key) + different fingerprint returns IDEMPOTENCY_CONFLICT.
- Currency Compatibility: request.currency == config.currency (conversion prohibited).
- Per-Transaction Limit: amount <= per_transaction_limit.
- Daily Cumulative Limit: daily_posted_sum + amount <= daily_limit on current UTC calendar day.
- Velocity Limit: qualifying outbound transfers in rolling window < velocity_count_limit.
- Step-Up Approval Check: If amount >= step_up_threshold, verifies trusted approval artifact bound to exact fingerprint.
- Fail-Closed: Limit breach or missing/mismatched approval evaluates to DENY / STEP_UP_REQUIRED.
- Invariant: Simulator mutation invocation count = 0.

       ↓ (Safety ALLOW: All Gates Passed)
[Layer 4: Business State & State Mutation (BankingSimulator)]
Question: "Is this transaction currently valid and executable in banking state?"
- Evaluates account status (ACCOUNT_FROZEN / ACCOUNT_INACTIVE).
- Evaluates monetary constraints (INSUFFICIENT_FUNDS).
- Evaluates failure injection (PRE_COMMIT_FAILURE).
- Executes atomic in-memory balance transition and records POSTED transaction.

       ↓ (Post-Execution Lifecycle)
[Gateway Post-Execution Commit]
- IF Simulator succeeds (POSTED):
    * Commit result to AuthoritativeIdempotencyStore.
    * Consume StepUpApproval token (prevents reuse).
- IF Simulator fails (Known failure: INSUFFICIENT_FUNDS / PRE_COMMIT_FAILURE):
    * Do NOT commit idempotency key (allows retry).
    * Do NOT consume StepUpApproval token (remains reusable for valid retry).
```

---

## Security Boundary Formulation

### Simulator-Bypass Security Claim
We cannot prove that Python's single-process execution environment makes direct access to the simulator impossible (any in-process code could theoretically instantiate or access `sim.transfer()` directly). 
What we **can and do prove through rigorous automated testing** is:
> `SecureExecutionGateway` never invokes simulator state mutation unless authentication, authorization, and transaction-safety gates have all evaluated to `ALLOW`. For every pre-execution denial, the simulator mutation invocation count is verified to be **strictly zero**.

---

## Explicit Boundaries for Future Phases

| Capability | Current Status | Target Phase | Boundary Enforcement |
|---|---|---|---|
| **Multi-Factor / Step-Up Auth** | `VERIFIED` | Phase 3 | Deterministic simulated approval bound to transaction fingerprint |
| **Transaction Safety & Limits** | `VERIFIED` | Phase 3 | Per-tx, daily cumulative, velocity limits, and currency enforcement |
| **Authoritative Idempotency** | `VERIFIED` | Phase 3 | Scoped to (principal_id, idempotency_key) with at-most-once semantics |
| **Fraud Detection ML** | `DEFERRED` | Phase 4 | Safety engine uses deterministic rules; ML deferred |
| **LLM Agent Orchestration** | `NOT IMPLEMENTED` | Phase 4 | Pure Python class-based API; zero LLM code in Phases 0-3 |
| **Model Context Protocol (MCP)** | `NOT IMPLEMENTED` | Phase 5 | In-process library calls; MCP server deferred |
| **Web APIs (FastAPI)** | `NOT IMPLEMENTED` | Future | In-process library calls only; no HTTP daemon |
| **Persistent DB (PostgreSQL)** | `NOT IMPLEMENTED` | Future | In-memory collections only; no relational database |
| **Real Banking Rails** | `NOT IMPLEMENTED` | Never | Simulated environment only; no external rails |
