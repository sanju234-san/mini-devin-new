"""
Retrieval Agent subpackage.

Responsible for locating relevant source files, test cases, and documentation
to supply context for the Planner and Coder agents.
"""

from app.agents.retrieval.agent import retrieval_node

__all__ = ["retrieval_node"]
