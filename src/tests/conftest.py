import os


def pytest_configure(config):
    """Opt-in local tracing for manually verifying pathfinder's OTEL wiring.

    pathfinder itself never calls trace.set_tracer_provider() in the parent
    process (see pathfinder/telemetry.py) -- that's left to whatever hosts it
    (Shepherd calls its own setup_tracer() for that). Running the test suite
    directly makes pytest the host, so without this, every span pathfinder
    creates in the parent process is a no-op with nowhere to go.

    No-op unless one of these is set, so normal `pytest` runs are unaffected:
      - PATHFINDER_OTEL_CONSOLE=1        print every span to stdout
      - OTEL_EXPORTER_OTLP_ENDPOINT=...  export via OTLP/gRPC, e.g. to a local
        Jaeger: docker run -p 4317:4317 -p 16686:16686 jaegertracing/all-in-one
        then OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
    Requires the `catrax-pathfinder[otel]` extra installed.
    """
    console = os.environ.get("PATHFINDER_OTEL_CONSOLE")
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not (console or otlp_endpoint):
        return

    from opentelemetry import trace
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: "pathfinder-tests"}))

    if console:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

    trace.set_tracer_provider(provider)

    # Auto-instrument `requests` so RetrieverRepo's POSTs get their own
    # client spans too, matching what a real host (e.g. Shepherd) sets up.
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    RequestsInstrumentor().instrument()
