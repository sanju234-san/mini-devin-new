"""
Triage Agent subpackage.

Classifies incoming GitHub issues as bug, feature, documentation, question,
or out of scope, routing unsupported requests to a safe termination path.
"""

from app.agents.triage.agent import triage_node

__all__ = ["triage_node"]
