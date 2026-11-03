"""
Reviewer Agent subpackage.

Compares generated code patches against the approved implementation plan,
performing static analysis and verification prior to PR generation.
"""

from app.agents.reviewer.agent import reviewer_node

__all__ = ["reviewer_node"]
