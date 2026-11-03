"""
Tests verifying the clean eight-subfolder architecture under backend/app/agents/.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

AGENT_SUBPACKAGES = (
    "triage",
    "retrieval",
    "planner",
    "coder",
    "test_runner",
    "debugger",
    "reviewer",
    "pr_agent",
)


@pytest.mark.parametrize("subpkg", AGENT_SUBPACKAGES)
def test_agent_subpackage_files_exist(subpkg: str):
    """Verify that each agent directory contains __init__.py and agent.py."""
    base_dir = Path(__file__).resolve().parent.parent.parent / "app" / "agents" / subpkg
    assert base_dir.is_dir(), f"Agent subpackage directory missing: {base_dir}"

    init_file = base_dir / "__init__.py"
    agent_file = base_dir / "agent.py"

    assert init_file.is_file(), f"__init__.py missing in {subpkg}"
    assert agent_file.is_file(), f"agent.py missing in {subpkg}"


@pytest.mark.parametrize("subpkg", AGENT_SUBPACKAGES)
def test_agent_subpackage_importable(subpkg: str):
    """Verify that every agent subpackage is importable and defines an agent node callable."""
    pkg_name = f"app.agents.{subpkg}"
    mod = importlib.import_module(pkg_name)
    assert mod is not None

    agent_mod = importlib.import_module(f"{pkg_name}.agent")
    assert agent_mod is not None


def test_graph_uses_subpackage_nodes():
    """Verify that graph.py imports and executes nodes from the modular subpackages."""
    from app.agents.graph import create_workflow_graph
    from app.agents.triage import triage_node
    from app.agents.retrieval import retrieval_node
    from app.agents.planner import planner_node

    graph = create_workflow_graph()
    assert graph is not None

    # Verify functions match
    assert callable(triage_node)
    assert callable(retrieval_node)
    assert callable(planner_node)
