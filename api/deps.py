"""Dependency injection: singleton graph instance."""

from medical_reader.graph import get_graph as _get_graph_fn


def get_graph():
    """Get the compiled LangGraph instance (singleton per process)."""
    return _get_graph_fn()
