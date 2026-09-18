"""
Authentication Context and Simulated Session Management.

TRUST BOUNDARY NOTICE:
- Session tokens are deterministic simulated credentials for the test environment.
- They are NOT cryptographically secure credentials.
- The security property demonstrated is that callers/agents cannot establish or alter
  principal identity through request parameters.
- Real authentication security (OAuth2, OIDC, JWT, password hashing) is explicitly out of scope.
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from banking_simulator.models import User, UserStatus
from banking_simulator.simulator import BankingSimulator


class AuthContext(BaseModel):
    """
    Immutable, sealed authentication context representing verified caller identity.

    Callers cannot alter this object after issuance. It must only be created by the
    SimulatedSessionManager after token resolution.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    principal_id: Optional[str] = Field(default=None, description="Resolved User ID if authenticated")
    authenticated: bool = Field(default=False, description="True only if resolved by session manager")
    session_id: Optional[str] = Field(default=None, description="Simulated session identifier")
    roles: list[str] = Field(default_factory=list, description="Roles assigned to this principal")


class SimulatedSessionManager:
    """
    Authoritative trust boundary for resolving simulated session tokens into AuthContext.

    Separation of Concerns:
    - Session provisioning (`provision_session`) is a trusted test/setup operation only.
      It is NEVER exposed to future agents, user requests, or gateway callers.
    - Authentication (`authenticate`) resolves an existing caller-supplied token against
      known sessions and simulator state.
    """

    DEFAULT_TEST_SESSIONS = {
        "token_alice": "user_001",
        "token_bob": "user_002",
        "token_suspended": "user_suspended_001",
    }

    def __init__(self, simulator: BankingSimulator):
        self._simulator = simulator
        # Internal token store: token -> user_id
        self._sessions: dict[str, str] = dict(self.DEFAULT_TEST_SESSIONS)

        # Ensure suspended user exists in simulator for security tests if not present
        if not self._simulator.get_user("user_suspended_001"):
            self._simulator._users["user_suspended_001"] = User(
                user_id="user_suspended_001",
                name="Suspended Sam",
                status=UserStatus.SUSPENDED,
            )

    # --------------------------------------------------------------------------
    # Trusted Setup / Test-Only Provisioning
    # --------------------------------------------------------------------------

    def provision_session(self, user_id: str, custom_token: Optional[str] = None) -> str:
        """
        Trusted test setup operation to register a session token for a simulated user.
        WARNING: Strictly test fixture provisioning. Never expose to callers or agents.
        """
        token = custom_token or f"sess_{user_id}_{len(self._sessions) + 1}"
        self._sessions[token] = user_id
        return token

    # --------------------------------------------------------------------------
    # Public Authentication Boundary
    # --------------------------------------------------------------------------

    def authenticate(self, session_token: Optional[str]) -> AuthContext:
        """
        Resolve a caller-provided session token into a trusted AuthContext.

        Decoupling Invariant:
        Authentication answers ONLY 'Who is the caller?'. A suspended user authenticates
        successfully (their identity is verified as that user). Authorization will independently
        evaluate their standing and deny protected operations.
        """
        if not session_token or not isinstance(session_token, str):
            return AuthContext(principal_id=None, authenticated=False, session_id=None, roles=[])

        user_id = self._sessions.get(session_token)
        if not user_id:
            # Unknown token -> unauthenticated
            return AuthContext(principal_id=None, authenticated=False, session_id=None, roles=[])

        # Principal identity verified
        return AuthContext(
            principal_id=user_id,
            authenticated=True,
            session_id=session_token,
            roles=["CUSTOMER"],
        )
