"""
Debugger Agent subpackage.

Analyzes test failures, traces error stacks, and orchestrates bounded retry loops
to guide the Coder Agent toward passing implementations.
"""

from app.agents.debugger.agent import debugger_node, diagnose_failure_details

__all__ = ["debugger_node", "diagnose_failure_details"]
