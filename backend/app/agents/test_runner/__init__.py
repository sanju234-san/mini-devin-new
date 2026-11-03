"""
Test Runner Agent subpackage.

Executes test suites inside isolated sandboxes (Docker / E2B) to evaluate
patch correctness and detect regressions.
"""

from app.agents.test_runner.agent import test_runner_node

__all__ = ["test_runner_node"]
