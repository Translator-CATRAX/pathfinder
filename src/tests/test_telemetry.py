import logging
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import pathfinder.Pathfinder as pathfinder_module
import pathfinder.PathRanker as path_ranker_module
import pathfinder.core.BidirectionalPathFinder as bidi_module
import pathfinder.telemetry as telemetry_module
from pathfinder.Pathfinder import Pathfinder
from pathfinder.PathRanker import PathRanker
from pathfinder.core.BidirectionalPathFinder import BidirectionalPathFinder
from pathfinder.telemetry import inject_context, submit_with_context


@pytest.fixture
def span_exporter(monkeypatch):
    """A fresh SDK tracer backed by an in-memory exporter, swapped into each
    instrumented module directly.

    `trace.get_tracer(...)` returns a `ProxyTracer` that resolves and caches
    its *real* delegate the first time any provider is active, then keeps
    that delegate forever -- swapping the global provider between tests would
    only affect whichever test runs first. Monkeypatching each module's
    `tracer` symbol sidesteps that and gives every test its own isolated
    exporter.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    fresh_tracer = provider.get_tracer("pathfinder-test")
    monkeypatch.setattr(pathfinder_module, "tracer", fresh_tracer)
    monkeypatch.setattr(path_ranker_module, "tracer", fresh_tracer)
    monkeypatch.setattr(bidi_module, "tracer", fresh_tracer)
    monkeypatch.setattr(telemetry_module, "tracer", fresh_tracer)
    yield exporter


def test_rank_path_creates_span(span_exporter):
    with patch.object(PathRanker, "_rank_path", return_value=({"ok": True}, [1, 2, 3])):
        path_ranker = PathRanker("sqlite:unused.sqlite", "sqlite:unused.sqlite", max_size=42)
        response, paths = path_ranker.rank_path({})

    assert response == {"ok": True}
    assert paths == [1, 2, 3]

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "pathfinder.rank_path"
    assert spans[0].attributes["pathfinder.max_size"] == 42
    assert spans[0].attributes["pathfinder.path_count"] == 3


def test_get_paths_creates_span_and_nests_children(span_exporter):
    logger = logging.getLogger("tests.telemetry")

    with patch.object(
        BidirectionalPathFinder, "find_all_paths", return_value=([], {"nodes": {}, "edges": {}})
    ), patch.object(
        Pathfinder, "post_paths_process", return_value=("result", "aux", "kg")
    ):
        pathfinder = Pathfinder(
            "retriever:http://unused",
            "sqlite:unused.sqlite",
            "sqlite:unused.sqlite",
            set(),
            set(),
            logger,
        )
        result = pathfinder.get_paths("A", "B", "n1", "n2")

    assert result == ("result", "aux", "kg")

    spans = span_exporter.get_finished_spans()
    names = {s.name for s in spans}
    assert "pathfinder.get_paths" in names
    root = next(s for s in spans if s.name == "pathfinder.get_paths")
    assert root.attributes["pathfinder.src_node_id"] == "A"
    assert root.attributes["pathfinder.dst_node_id"] == "B"


def test_find_all_paths_same_node_short_circuits_but_still_spans(span_exporter):
    logger = logging.getLogger("tests.telemetry")
    finder = BidirectionalPathFinder("retriever:http://unused", "sqlite:a", "sqlite:b", 30, 30000, logger)
    result = finder.find_all_paths("SAME", "SAME", hops_numbers=4)

    assert result == set()
    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "pathfinder.find_all_paths"


def test_submit_with_context_propagates_current_span(span_exporter):
    def record_current_span():
        return trace.get_current_span().get_span_context()

    with telemetry_module.tracer.start_as_current_span("pathfinder.test_parent") as parent_span:
        parent_trace_id = parent_span.get_span_context().trace_id
        assert parent_span.get_span_context().is_valid
        with ThreadPoolExecutor(max_workers=1) as executor:
            # Bare executor.submit would NOT see the current span (each thread
            # gets its own contextvars), so assert the naive path is broken
            # before proving submit_with_context fixes it.
            bare_future = executor.submit(record_current_span)
            assert bare_future.result().trace_id != parent_trace_id

            future = submit_with_context(executor, record_current_span)
            child_ctx = future.result()

    assert child_ctx.is_valid
    assert child_ctx.trace_id == parent_trace_id


def test_inject_and_extract_context_round_trip(span_exporter):
    from opentelemetry import propagate

    with telemetry_module.tracer.start_as_current_span("pathfinder.test_carrier") as span:
        expected_trace_id = span.get_span_context().trace_id
        carrier = inject_context()

    assert carrier, "expected a non-empty W3C traceparent carrier"
    extracted_ctx = propagate.extract(carrier)
    extracted_span = trace.get_current_span(extracted_ctx)
    assert extracted_span.get_span_context().trace_id == expected_trace_id
