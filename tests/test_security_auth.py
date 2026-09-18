"""
Tests for Authentication Context and Session Boundary (src/banking_security/context.py).
"""

import pytest
from pydantic import ValidationError

from banking_security.context import AuthContext, SimulatedSessionManager
from banking_simulator.simulator import BankingSimulator


def test_valid_token_authentication():
    sim = BankingSimulator(seed_default_fixtures=True)
    mgr = SimulatedSessionManager(sim)

    ctx = mgr.authenticate("token_alice")
    assert ctx.authenticated is True
    assert ctx.principal_id == "user_001"
    assert ctx.session_id == "token_alice"
    assert "CUSTOMER" in ctx.roles


def test_unknown_token_returns_unauthenticated():
    sim = BankingSimulator(seed_default_fixtures=True)
    mgr = SimulatedSessionManager(sim)

    ctx = mgr.authenticate("invalid_token_999")
    assert ctx.authenticated is False
    assert ctx.principal_id is None
    assert ctx.session_id is None
    assert len(ctx.roles) == 0


def test_none_token_returns_unauthenticated():
    sim = BankingSimulator(seed_default_fixtures=True)
    mgr = SimulatedSessionManager(sim)

    ctx = mgr.authenticate(None)
    assert ctx.authenticated is False
    assert ctx.principal_id is None


def test_auth_context_immutability():
    """Verify that AuthContext cannot be modified after issuance."""
    ctx = AuthContext(principal_id="user_001", authenticated=True, session_id="tok", roles=["CUSTOMER"])
    with pytest.raises(ValidationError):
        ctx.principal_id = "user_002"  # type: ignore


def test_auth_context_extra_forbid():
    """Verify that callers cannot inject arbitrary metadata into AuthContext."""
    with pytest.raises(ValidationError):
        AuthContext(principal_id="user_001", authenticated=True, forged_claim="admin")  # type: ignore


def test_suspended_user_authentication():
    """
    Decoupling Invariant:
    A suspended user authenticates successfully (identity is verified).
    Authorization will independently evaluate their standing and deny protected operations.
    """
    sim = BankingSimulator(seed_default_fixtures=True)
    mgr = SimulatedSessionManager(sim)

    ctx = mgr.authenticate("token_suspended")
    assert ctx.authenticated is True
    assert ctx.principal_id == "user_suspended_001"
