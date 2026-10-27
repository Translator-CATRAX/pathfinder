# catrax-pathfinder

`catrax-pathfinder` is a Python package for discovering and returning candidate paths between two CURIE nodes using a Biological Knowledge Graph and precomputed databases (NGD and node degree). It supports **SQLite** and **MySQL** backends for both the NGD and degree repositories via a simple URL prefix.

---

## Installation

```bash
pip install catrax-pathfinder
```

---

## Obtain databases

You will need a compatible curie_ngd and tier0-info-for-overlay SQLite database for the KG version you are using.

- **Recommended**: Ask a team member for mysql urls to these databases
- **Alternative**: Ask a team member for local copies of these databases



## Quickstart

```python
from pathfinder.Pathfinder import Pathfinder

repo_uri = "retriever:<retriever_URL>"

ngd_url = "sqlite:curie_ngd_v1.0_tier0-20260621.sqlite"
degree_url = "sqlite:tier0-info-for-overlay_v1.0_tier0-20260621"

# Optional filters
blocked_curies = set([
    # "CHEBI:1234",
])
blocked_synonyms = set([
    # "aspirin",
])

# Any logger-like object is acceptable (e.g., a Python logging.Logger)
logger = None

pathfinder = Pathfinder(
    repo_uri=repo_uri,
    ngd_url=ngd_url,
    degree_url=degree_url,
    blocked_curies=blocked_curies,
    blocked_synonyms=blocked_synonyms,
    logger=logger,
)

result, aux_graphs, knowledge_graph = pathfinder.get_paths(
    src_node_id="MONDO:0005148",
    dst_node_id="CHEBI:15365",
    src_pinned_node="node_1",
    dst_pinned_node="node_2",
    hops_numbers=4,
    max_hops_to_explore=4,
    limit=500,
    prune_top_k=75,
    degree_threshold=10000,
    category_constraints=[],
)
```

---

## API

### `Pathfinder(...)`

Constructor:

```python
Pathfinder(
    repo_uri: str,
    ngd_url: str,
    degree_url: str,
    blocked_curies: Set[str],
    blocked_synonyms: Set[str],
    logger,
)
```

#### Parameters

- **repo_uri**: A URL to Retriever.
- **ngd_url**: Connection string for the *CURIE-NGD* repository (SQLite or MySQL).
- **degree_url**: Connection string for the *node degree* repository (SQLite or MySQL).
- **blocked_curies**: A set of CURIE IDs; any path that passes through these CURIEs is dropped.
- **blocked_synonyms**: A set of strings; any path that passes through nodes whose names match these values is dropped.
- **logger**: A logger-like object used for logging.

---

### `get_paths(...)`

```python
get_paths(
    src_node_id: str,
    dst_node_id: str,
    src_pinned_node: str,
    dst_pinned_node: str,
    hops_numbers: int = 4,
    max_hops_to_explore: int = 6,
    limit: int = 500,
    prune_top_k: int = 30,
    degree_threshold: int = 30000,
    category_constraints: Set[str] = None
)
```

#### Parameters

- **src_node_id**: Source CURIE ID.
- **dst_node_id**: Destination CURIE ID.
- **src_pinned_node**: Source pinned node ID.
- **dst_pinned_node**: Destination pinned node ID.
- **hops_numbers**: Maximum number of hops a returned path can have.
- **max_hops_to_explore**: Maximum depth to explore during expansion; after exploration, paths longer than `hops_numbers` are removed.
- **limit**: Maximum number of paths to return.
- **prune_top_k**: During each expansion step, neighbors are ranked and only the top `k` are kept for further expansion.
- **degree_threshold**: Nodes with degree greater than this threshold are not expanded.
- **category_constraints** *(optional)*: If non-empty, keeps only paths that contain at least one of these categories.

#### Returns

`get_paths(...)` returns a 3-tuple of TRAPI-compliant objects.

These correspond to standard Translator Reasoner API (TRAPI) result structures:
For more details on TRAPI object formats and the overall API specification, see the TRAPI documentation on GitHub: https://github.com/NCATSTranslator/ReasonerAPI

```python
(result, aux_graphs, knowledge_graph)
```



---

## Repository URL formats (SQLite and MySQL)

Both `ngd_url` and `degree_url` accept a backend prefix.

### SQLite

Use `sqlite:` followed by the SQLite filename/path.

- NGD example:
  - `sqlite:curie_ngd_v1.0_KG2.10.2.sqlite`
- Degree example:
  - `sqlite:kg2c_v1.0_KG2.10.2.sqlite`

### MySQL

Use `mysql:` followed by your MySQL config string.

- NGD example:
  - `mysql:arax-databases-mysql.rtx.ai:public_ro:curie_ngd_v1_0_kg2_10_2`
- Degree example:
  - `mysql:arax-databases-mysql.rtx.ai:public_ro:kg2c_v1_0_kg2_10_2`

> The package automatically detects which backend to use based on the `sqlite:` / `mysql:` prefix.

---

## Notes & tips

- Start with smaller `hops_numbers` and `limit` if you are experimenting, then scale up.
- If exploration grows too quickly on high-degree nodes, consider lowering `degree_threshold` and/or `prune_top_k`.
- Use `blocked_curies` and `blocked_synonyms` to remove known “noisy” nodes and keep path results cleaner.

---

## Tracing (OpenTelemetry)

`pathfinder` emits [OpenTelemetry](https://opentelemetry.io/) spans for its
key phases (`get_paths`, `get_three_hops_paths`, `find_all_paths`,
`find_three_hops_paths`, `rank_path`) via `trace.get_tracer("pathfinder")`.
It only ever *reads* the current tracer provider — it never configures one
in your process — so:

- **Used inside an app that already configures an OTEL SDK** (e.g.
  [Shepherd](https://github.com/BioPack-team/shepherd)): pathfinder's spans
  just show up, nested under whatever span was active when you called
  `get_paths`/`get_three_hops_paths`. If that app also instruments the
  `requests` library (e.g. via `RequestsInstrumentor().instrument()`), the
  Retriever HTTP calls in `RetrieverRepo` get their own client spans for free.
- **Used standalone**: install the `otel` extra and point it at a collector:

  ```bash
  pip install "catrax-pathfinder[otel]"
  export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
  ```

  With that in place, pathfinder configures tracing itself where it has to:
  `get_paths()` runs its bidirectional search in two child processes
  (`ProcessPoolExecutor`), and a freshly spawned process shares no state with
  its parent, so it can't just inherit whatever tracer provider your app set
  up. pathfinder bootstraps a minimal one in each child (gated on
  `OTEL_EXPORTER_OTLP_ENDPOINT` being set, so this is a no-op otherwise) and
  propagates the parent span's context into it, so the Retriever calls made
  from inside the search show up correctly nested under `get_paths` in your
  trace viewer.

  For quick local checks without a collector, set `PATHFINDER_OTEL_CONSOLE=1`
  instead (or alongside `OTEL_EXPORTER_OTLP_ENDPOINT`) to print every span —
  parent-process *and* the two `ProcessPoolExecutor` children's — as JSON to
  stdout. Note that setting `PATHFINDER_OTEL_CONSOLE`/`OTEL_EXPORTER_OTLP_ENDPOINT`
  only reaches those `ProcessPoolExecutor` children automatically; if *your*
  app also configures its own `TracerProvider` in its main process, that's
  still your app's job (mirroring `OTEL_EXPORTER_OTLP_ENDPOINT`/Shepherd's own
  `setup_tracer()` — pathfinder never calls `set_tracer_provider()` itself
  outside those spawned children).

No environment variable set, no SDK installed ⇒ every span is a no-op with
zero overhead — existing usage is unaffected.

---


