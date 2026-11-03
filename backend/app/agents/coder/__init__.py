"""
Coder Agent subpackage.

Responsible for generating targeted, constrained code edits and patches
conforming to the human-approved implementation plan.
"""

from app.agents.coder.agent import coder_node

__all__ = ["coder_node"]
