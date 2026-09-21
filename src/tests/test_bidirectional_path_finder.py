import logging
from concurrent.futures import Future
from unittest.mock import patch

import pytest

import pathfinder.core.BidirectionalPathFinder as bidi_module
from pathfinder.core.BidirectionalPathFinder import BidirectionalPathFinder
from pathfinder.core.model.PathContainer import PathContainer

LOGGER = logging.getLogger("tests.bidirectional_path_finder")


class _FakeExecutor:
    """Stand-in for ProcessPoolExecutor that resolves futures synchronously,
    so these tests exercise find_all_paths' own error handling without
    spawning real processes or needing a reachable Retriever/sqlite DB."""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def submit(self, fn, *args, **kwargs):
        # run_bfs_process(hops_numbers, node_id, repo_args, prune_top_k, degree_threshold, otel_carrier)
        node_id = args[1]
        future = Future()
        outcome = self._results_by_node[node_id]
        if isinstance(outcome, Exception):
            future.set_exception(outcome)
        else:
            future.set_result(outcome)
        return future


def _executor_factory(results_by_node):
    def factory(*args, **kwargs):
        ex = _FakeExecutor()
        ex._results_by_node = results_by_node
        return ex
    return factory


def _finder():
    return BidirectionalPathFinder(
        "retriever:http://unreachable", "sqlite:a", "sqlite:b", 30, 30000, LOGGER
    )


def test_both_bfs_processes_failing_raises_clear_error():
    results = {
        "CHEBI:45783": RuntimeError("simulated retriever connection failure"),
        "MONDO:0004979": RuntimeError("simulated retriever connection failure"),
    }
    with patch.object(bidi_module, "ProcessPoolExecutor", _executor_factory(results)):
        with pytest.raises(RuntimeError) as exc_info:
            _finder().find_all_paths("CHEBI:45783", "MONDO:0004979", hops_numbers=4)

    assert "CHEBI:45783" in str(exc_info.value)
    assert "MONDO:0004979" in str(exc_info.value)


def test_one_bfs_process_failing_raises_clear_error():
    results = {
        "CHEBI:45783": RuntimeError("simulated retriever connection failure"),
        "MONDO:0004979": (PathContainer(), {"nodes": {}, "edges": {}}),
    }
    with patch.object(bidi_module, "ProcessPoolExecutor", _executor_factory(results)):
        with pytest.raises(RuntimeError) as exc_info:
            _finder().find_all_paths("CHEBI:45783", "MONDO:0004979", hops_numbers=4)

    assert "CHEBI:45783" in str(exc_info.value)
    assert "MONDO:0004979" not in str(exc_info.value)


def test_both_bfs_processes_succeeding_returns_normally():
    results = {
        "CHEBI:45783": (PathContainer(), {"nodes": {}, "edges": {}}),
        "MONDO:0004979": (PathContainer(), {"nodes": {}, "edges": {}}),
    }
    with patch.object(bidi_module, "ProcessPoolExecutor", _executor_factory(results)):
        result, kg = _finder().find_all_paths("CHEBI:45783", "MONDO:0004979", hops_numbers=4)

    assert result == []
    assert kg == {"nodes": {}, "edges": {}}
