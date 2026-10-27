import contextvars
import os

from opentelemetry import propagate, trace

tracer = trace.get_tracer("pathfinder")

_CHILD_PROVIDER = None  # set only inside a spawned ProcessPoolExecutor child


def inject_context() -> dict:
    """W3C traceparent carrier for the current span, to hand to a child process."""
    carrier: dict = {}
    propagate.inject(carrier)
    return carrier


def submit_with_context(executor, fn, *args, **kwargs):
    """executor.submit that carries the caller's contextvars (incl. the current
    OTEL span) into the worker thread -- ThreadPoolExecutor does not do this
    by default, so without it spans created inside `fn` become orphaned roots."""
    ctx = contextvars.copy_context()
    return executor.submit(ctx.run, fn, *args, **kwargs)


def child_bootstrap(carrier: dict):
    """Call at the top of a spawned ProcessPoolExecutor worker.

    A spawned child is a fresh interpreter: it shares no state with the
    parent, so even if the host process (e.g. Shepherd) configured a
    TracerProvider, this child has none. This bootstraps a minimal one so the
    child's spans are still exported, and extracts the parent span context
    from `carrier` so they nest under the call that submitted this worker.

    No-ops (spans stay non-recording) unless OTEL_EXPORTER_OTLP_ENDPOINT
    and/or PATHFINDER_OTEL_CONSOLE=1 is set AND the optional
    `catrax-pathfinder[otel]` extras are installed -- silent and free for
    every user who hasn't opted in. PATHFINDER_OTEL_CONSOLE alone (e.g. set
    by src/tests/conftest.py) only reaches the *parent* process by default --
    a spawned child never runs that setup -- so it's honored here too; a
    spawned child inherits the parent's stdout, so printed spans still land
    in the same terminal.
    """
    global _CHILD_PROVIDER
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    console = os.environ.get("PATHFINDER_OTEL_CONSOLE")
    if _CHILD_PROVIDER is None and (otlp_endpoint or console):
        try:
            from opentelemetry.instrumentation.requests import RequestsInstrumentor
            from opentelemetry.sdk.resources import SERVICE_NAME, Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import (
                BatchSpanProcessor,
                SimpleSpanProcessor,
            )
        except ImportError:
            pass
        else:
            provider = TracerProvider(
                resource=Resource.create({SERVICE_NAME: "pathfinder-bfs-worker"})
            )
            if otlp_endpoint:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )
                provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
            if console:
                from opentelemetry.sdk.trace.export import ConsoleSpanExporter
                provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
            trace.set_tracer_provider(provider)
            RequestsInstrumentor().instrument()
            _CHILD_PROVIDER = provider
    return trace.get_tracer("pathfinder"), propagate.extract(carrier)


def flush_child() -> None:
    """Flush the child's span processor before the spawned process exits.

    A spawned ProcessPoolExecutor worker can be torn down as soon as it
    returns, before a BatchSpanProcessor's background thread gets a chance to
    export -- without this, the child's spans are silently lost.
    """
    if _CHILD_PROVIDER is not None:
        _CHILD_PROVIDER.force_flush()
