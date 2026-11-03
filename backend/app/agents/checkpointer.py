"""
LangGraph Checkpointing Service for Mini-Devin.

Provides checkpointer instances and persistence management for stateful
graph execution, human-in-the-loop approval, and workflow resume.

Limitations of In-Memory Checkpointing:
---------------------------------------
LangGraph's ``MemorySaver`` retains state within active Python process memory:
1. It does NOT provide durable persistence across server restarts or crashes.
2. It cannot be shared across multiple process instances or worker nodes.
3. For production deployments, replace this checkpointer with a database-backed
   saver such as ``langgraph.checkpoint.postgres.PostgresSaver``.
"""

from __future__ import annotations

import logging
from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

_DEFAULT_CHECKPOINTER: Optional[BaseCheckpointSaver] = None


def create_checkpointer() -> BaseCheckpointSaver:
    """
    Create a new in-memory checkpointer instance.
    
    Useful for isolated test runs and test suites that require a clean state.
    """
    return MemorySaver()


def get_checkpointer() -> BaseCheckpointSaver:
    """
    Return the global shared checkpointer instance, initializing if necessary.
    
    This provides stable cross-invocation thread retention within the local process.
    """
    global _DEFAULT_CHECKPOINTER
    if _DEFAULT_CHECKPOINTER is None:
        logger.info("Initializing in-memory MemorySaver checkpointer")
        _DEFAULT_CHECKPOINTER = MemorySaver()
    return _DEFAULT_CHECKPOINTER


def set_checkpointer(checkpointer: BaseCheckpointSaver) -> None:
    """Set or override the active checkpointer instance (e.g. for testing)."""
    global _DEFAULT_CHECKPOINTER
    _DEFAULT_CHECKPOINTER = checkpointer


def reset_checkpointer() -> None:
    """Reset the global checkpointer instance, clearing all in-memory threads."""
    global _DEFAULT_CHECKPOINTER
    _DEFAULT_CHECKPOINTER = None
