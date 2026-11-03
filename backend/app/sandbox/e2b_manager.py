"""E2B (Firecracker microVM) sandbox manager stub.

Plain-Language Guide & Architecture Evaluation:
----------------------------------------------
E2B (https://e2b.dev) is a cloud sandbox platform providing ephemeral microVMs
isolated via AWS Firecracker. While our default development sandbox runs locally
via Docker, E2B is planned for deployment on platforms like Render where a local
Docker daemon is not accessible.

Evaluation Criteria for Future E2B Implementation:
--------------------------------------------------
1. Hardware-level Isolation:
   Firecracker microVMs provide real kernel-level hardware virtualization, whereas
   Docker containers share the host Linux kernel.
2. Startup Latency:
   E2B microVMs boast sub-second spin-up (~150-300ms), competitive with local Docker containers.
3. Cost & Free Tier Considerations:
   Docker runs locally for free; E2B requires paid cloud compute or usage-capped free tiers.
4. API Key & Credential Handling:
   Requires secure injection of E2B_API_KEY via environment variables and strict egress control.
5. Cloud Deployment Feasibility:
   Runs effortlessly on PaaS hosts (Render, Fly.io, Heroku) without requiring privileged
   Docker-in-Docker or exposure of the Docker Unix socket.

Note: This stub implements the `SandboxManager` protocol but raises
`SandboxUnavailableError` because E2B integration is scheduled for a future milestone.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.sandbox.base import OutputCallback, SandboxManager, SandboxUnavailableError
from app.sandbox.models import SandboxRunRequest, SandboxRunResult

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class E2BSandboxManager(SandboxManager):
    """Stub implementation of SandboxManager for E2B microVMs."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(
        self,
        request: SandboxRunRequest,
        on_output: OutputCallback | None = None,
    ) -> SandboxRunResult:
        """Execute run in an E2B microVM (Not Implemented)."""
        raise SandboxUnavailableError(
            "E2B backend not implemented. Use 'docker' backend or configure E2B integration."
        )

    async def destroy_all(self) -> None:
        """Destroy all active E2B microVMs (No-Op)."""
        pass

    async def ping(self) -> bool:
        """Check if E2B service is reachable (returns False for stub)."""
        return False
