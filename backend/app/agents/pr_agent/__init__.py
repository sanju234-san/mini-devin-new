"""
PR Agent subpackage.

Constructs comprehensive pull requests with issue references, test results,
and verification summaries. Strictly forbidden from merging pull requests.
"""

from app.agents.pr_agent.agent import pr_node

__all__ = ["pr_node"]
