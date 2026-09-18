# Secure Agentic Banking Assistant

> **Research Principle:** *"LLMs reason; deterministic systems enforce."*  
> **Simulation Boundary:** This project is a research evaluation and simulated environment only. There are no connections to real banking accounts, payment rails, or production financial infrastructure.

---

## Current Status: Phase 3 — Transaction Safety & Deterministic Execution Gate (Verified)

This repository contains four cleanly separated, deterministic layers:
1. **`banking_eval` (Phase 0: Frozen)**: An evaluation foundation that canonicalizes test schemas, computes deterministic metrics (Accuracy, Macro-F1), and enforces framework-level safety vetoes.
2. **`banking_simulator` (Phase 1: Frozen)**: A deterministic in-memory synthetic banking state machine providing exact Decimal accounting, isolated state, read operations, transfers, card freeze, failure injection, and idempotency tracking.
3. **`banking_security` (Phase 2: Frozen)**: A deterministic security layer enforcing an immutable authentication trust boundary (`SimulatedSessionManager`), decoupled authorization policies (`DeterministicPolicyEngine`), confused-deputy protection, and an authoritative gateway facade (`SecureBankingGateway`).
4. **`banking_safety` (Phase 3: Verified)**: A deterministic transaction safety and execution gate enforcing mandatory idempotency keys, sub-cent precision rejection, authoritative single-process idempotency replay/conflict detection, limits (per-tx, daily, velocity), tamper-evident step-up approval workflows, and an unbypassable execution gate (`SecureExecutionGateway`).

---

## Project Structure

```
project/
├── .gitignore                          # Git hygiene for .venv, caches, reports
├── pyproject.toml                      # Package configuration (Python >= 3.13)
├── README.md                           # Project overview & quickstart guide
├── CURRENT_PHASE.md                    # Current phase status and acceptance checklist
├── ARCHITECTURE.md                     # Living architecture documentation & boundaries
├── DECISIONS.md                        # Architecture Decision Records (ADR-001 to ADR-015)
├── TESTING.md                          # Test inventory, exact commands, and verified logs
├── CHANGELOG.md                        # Chronological release and phase history
├── src/
│   ├── banking_eval/                   # [Phase 0 - FROZEN] Evaluation Foundation
│   │   ├── schema.py                   # Canonical typed evaluation schemas (Pydantic)
│   │   ├── adapter.py                  # Dataset adapter interface & synthetic adapter
│   │   ├── baseline.py                 # Deterministic keyword/rule baseline classifier
│   │   ├── metrics.py                  # Pure-Python deterministic metrics calculation
│   │   ├── runner.py                   # Evaluation runner & safety-veto enforcement
│   │   └── reporting.py                # Human-readable & JSON report CLI generator
│   ├── banking_simulator/              # [Phase 1 - FROZEN] Synthetic Banking Simulator
│   │   ├── clock.py                    # Deterministic SimulatedClock (fixed epoch)
│   │   ├── models.py                   # Typed domain models (User, Account, Beneficiary, etc.)
│   │   ├── contracts.py                # OperationResult[T], ErrorCode, FailureMode
│   │   ├── fixtures.py                 # Isolated deterministic default seed data
│   │   ├── simulator.py                # BankingSimulator core state machine
│   │   └── demo.py                     # CLI verification demo (Tests A-E)
│   ├── banking_security/               # [Phase 2 - FROZEN] Security & Policy Layer
│   │   ├── context.py                  # Immutable AuthContext & SimulatedSessionManager
│   │   ├── actions.py                  # BankingAction, ResourceType, ResourceTarget
│   │   ├── contracts.py                # PolicyDecision, PolicyReasonCode, PolicyResult
│   │   ├── engine.py                   # DeterministicPolicyEngine (rule evaluation)
│   │   ├── gateway.py                  # SecureBankingGateway (authorized simulator facade)
│   │   └── demo.py                     # Security verification CLI demo (DEMO 1-7)
│   └── banking_safety/                 # [Phase 3 - VERIFIED] Transaction Safety & Execution Gate
│       ├── contracts.py                # SafetyDecision, SafetyReasonCode, GateStage, ExecutionGateResult
│       ├── request.py                  # TransactionRequest (strict Decimal, idempotency, fingerprinting)
│       ├── config.py                   # TransactionSafetyConfig (limits, thresholds, currency)
│       ├── limits.py                   # TransactionLimitEvaluator (per-tx, daily, velocity)
│       ├── idempotency.py              # AuthoritativeIdempotencyStore (principal-scoped at-most-once)
│       ├── approval.py                 # StepUpApproval & SimulatedStepUpApprovalService (non-burn lifecycle)
│       ├── engine.py                   # TransactionSafetyEngine (strict deterministic precedence)
│       ├── gateway.py                  # SecureExecutionGateway (4-layer unbypassable facade)
│       └── demo.py                     # Safety verification CLI demo (DEMO 1-8)
├── datasets/
│   └── synthetic_banking_intents.json  # Documented synthetic banking test cases
└── tests/
    ├── test_schema.py                  # [Phase 0] Canonical schema validation
    ├── test_adapter.py                 # [Phase 0] Adapter field mapping
    ├── test_baseline.py                # [Phase 0] Baseline determinism
    ├── test_metrics.py                 # [Phase 0] Mathematical metric verification
    ├── test_runner.py                  # [Phase 0] Evaluation runner execution
    ├── test_safety_veto.py             # [Phase 0] Independent safety-veto tests
    ├── test_simulator_models.py        # [Phase 1] Decimal exactness & model validation
    ├── test_simulator_reads.py         # [Phase 1] Read operations & ownership preservation
    ├── test_simulator_transfers.py     # [Phase 1] Transfers, frozen checks, conservation
    ├── test_simulator_cards.py         # [Phase 1] Card freeze state transitions
    ├── test_simulator_failure_injection.py # [Phase 1] Pre-commit failure injection
    ├── test_simulator_idempotency.py   # [Phase 1] Idempotency & clock determinism
    ├── test_security_auth.py           # [Phase 2] Session resolution & immutability
    ├── test_security_authorization.py  # [Phase 2] Deterministic authorization policies
    ├── test_security_confused_deputy.py # [Phase 2] Confused-deputy mitigation
    ├── test_security_gateway.py        # [Phase 2] Gateway facade & authorized dispatch
    ├── test_security_layer_separation.py # [Phase 2] Layer 2 vs Layer 3 separation
    ├── test_transaction_request.py     # [Phase 3] TransactionRequest validation & fingerprinting
    ├── test_transaction_limits.py      # [Phase 3] Currency, per-tx, daily, velocity limit tests
    ├── test_transaction_idempotency.py # [Phase 3] Authoritative idempotency store tests
    ├── test_transaction_approval.py    # [Phase 3] Step-up approval binding, expiry, non-burn
    ├── test_transaction_safety_engine.py # [Phase 3] Evaluation precedence & short-circuits
    ├── test_transaction_execution_gate.py # [Phase 3] 4-layer gateway & zero-mutation invariant
    └── test_transaction_security.py    # [Phase 3] Threat model & security metrics suite
```

---

## Environment Setup

### Verified Python Environment
- **Python 3.13.4** (verified on Windows). Compatibility with other versions is not claimed unless tested.

### Installation
1. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install the project and dependencies in editable mode:
   ```powershell
   .\.venv\Scripts\pip.exe install -e ".[dev]"
   ```

Minimal dependencies: `pydantic>=2.7.0`, `pytest>=8.0.0`. Zero heavy ML/agent packages.

---

## How to Run Tests

Run the complete test suite (136 tests: 35 Phase 0 + 27 Phase 1 + 31 Phase 2 + 43 Phase 3):
```powershell
.\.venv\Scripts\pytest.exe -v
```

---

## Running the Applications

### 1. Run Phase 3 Safety & Execution Gate Demo (DEMO 1–8)
```powershell
.\.venv\Scripts\python.exe -m banking_safety.demo
```
Demonstrates safe transfer, per-transaction limit enforcement, daily cumulative limit, velocity rolling window, step-up approval workflow, tampered/mismatched approval rejection, authoritative idempotency replay vs conflict, and simulator failure containment with approval non-burn.

### 2. Run Phase 2 Security & Policy Demo (DEMO 1–7)
```powershell
.\.venv\Scripts\python.exe -m banking_security.demo
```
Demonstrates unauthenticated rejection, authorized read, cross-user snooping denial, direct transfer with target semantics, confused-deputy prevention, suspended user authentication vs. authorization, and Layer 2/Layer 3 separation.

### 3. Run Phase 1 Simulator Demo (Tests A–E)
```powershell
.\.venv\Scripts\python.exe -m banking_simulator.demo
```
Demonstrates read operations, successful transfer with balance conservation, insufficient funds rejection, pre-commit failure injection, and card freeze.

### 4. Run Phase 0 Evaluation Harness
```powershell
.\.venv\Scripts\python.exe -m banking_eval.reporting --demo-mode normal
```
Outputs human-readable report table and writes structured JSON to `reports/evaluation_report.json`.
Outputs human-readable report table and writes structured JSON to `reports/evaluation_report.json`.

---

## Living Documentation (Project Source of Truth)

Please consult the project documentation for in-depth information:
- [CURRENT_PHASE.md](file:///f:/Agentic%20AI%20hackathon/project/CURRENT_PHASE.md): Active phase status, verified items, and acceptance checklist.
- [ARCHITECTURE.md](file:///f:/Agentic%20AI%20hackathon/project/ARCHITECTURE.md): System architecture, component boundaries, and future-phase limits.
- [DECISIONS.md](file:///f:/Agentic%20AI%20hackathon/project/DECISIONS.md): Architectural Decision Records (ADRs).
- [TESTING.md](file:///f:/Agentic%20AI%20hackathon/project/TESTING.md): Test inventory, exact commands, and verified output logs.
- [CHANGELOG.md](file:///f:/Agentic%20AI%20hackathon/project/CHANGELOG.md): Chronological record of changes.

---

## What is Intentionally NOT Implemented
- No LLMs, generative models, or prompts
- No agent frameworks (LangGraph, LangChain, AutoGen)
- No Model Context Protocol (MCP)
- No vector databases or RAG (pgvector, Chroma)
- No relational databases (PostgreSQL, SQLite)
- No web/HTTP frameworks (FastAPI, Flask)
- No real banking payment rails or credentials
