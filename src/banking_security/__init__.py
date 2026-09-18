"""
Banking Security Package.

Deterministic authentication and authorization layer.
Implements trusted authentication context, deterministic policy evaluation,
and authorized gateway facade. Zero LLMs, zero ML models.
"""

from banking_security.actions import BankingAction, ResourceTarget, ResourceType
from banking_security.context import AuthContext, SimulatedSessionManager
from banking_security.contracts import PolicyDecision, PolicyReasonCode, PolicyResult
from banking_security.engine import DeterministicPolicyEngine
from banking_security.gateway import SecureBankingGateway

__all__ = [
    "AuthContext",
    "BankingAction",
    "DeterministicPolicyEngine",
    "PolicyDecision",
    "PolicyReasonCode",
    "PolicyResult",
    "ResourceTarget",
    "ResourceType",
    "SecureBankingGateway",
    "SimulatedSessionManager",
]
