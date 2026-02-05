# catrax-pathfinder

`catrax-pathfinder` is a Python package for discovering and returning candidate paths between two CURIE nodes using a PloverDB endpoint and precomputed databases (NGD and node degree). It supports **SQLite** and **MySQL** backends for both the NGD and degree repositories via a simple URL prefix.

---

## Installation

```bash
pip install catrax-pathfinder
```

---

## Quickstart

```python
# If your package exposes Pathfinder at a different import path, adjust accordingly.
from catrax_pathfinder import Pathfinder  # e.g., from catrax_pathfinder.pathfinder import Pathfinder

plover_url = "https://kg2cploverdb.ci.transltr.io"

ngd_url = "sqlite:curie_ngd_v1.0_KG2.10.2.sqlite"
degree_url = "sqlite:kg2c_v1.0_KG2.10.2.sqlite"

# Optional filters
blocked_curies = [
    # "CHEBI:1234",
]
blocked_synonyms = [
    # "aspirin",
]

# Any logger-like object is acceptable (e.g., a Python logging.Logger)
logger = None

pathfinder = Pathfinder(
    repository_name="MLRepo",
    plover_url=plover_url,
    ngd_url=ngd_url,
    degree_url=degree_url,
    blocked_curies=blocked_curies,
    blocked_synonyms=blocked_synonyms,
    logger=logger,
)

result, aux_graphs, knowledge_graph = pathfinder.get_paths(
    src_node_id="MONDO:0005148",
    dst_node_id="CHEBI:15365",
    src_pinned_node="MONDO:0005148",
    dst_pinned_node="CHEBI:15365",
    hops_numbers=4,
    max_hops_to_explore=6,
    limit=500,
    prune_top_k=30,
    degree_threshold=30000,
    category_constraints=[],
)
```

---

## API

### `Pathfinder(...)`

Constructor:

```python
Pathfinder(
    repository_name,
    plover_url,
    ngd_url,
    degree_url,
    blocked_curies,
    blocked_synonyms,
    logger,
)
```

#### Parameters

- **repository_name**: For now, this should always be `"MLRepo"`.
- **plover_url**: URL of the PloverDB endpoint (example: `https://kg2cploverdb.ci.transltr.io`).
- **ngd_url**: Connection string for the *CURIE-NGD* repository (SQLite or MySQL).
- **degree_url**: Connection string for the *node degree* repository (SQLite or MySQL).
- **blocked_curies**: A list of CURIE IDs; any path that passes through these CURIEs is dropped.
- **blocked_synonyms**: A list of strings; any path that passes through nodes whose names match these values is dropped.
- **logger**: A logger-like object used for logging.

---

### `get_paths(...)`

```python
get_paths(
    src_node_id,
    dst_node_id,
    src_pinned_node,
    dst_pinned_node,
    hops_numbers=4,
    max_hops_to_explore=6,
    limit=500,
    prune_top_k=30,
    degree_threshold=30000,
    category_constraints=[],
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
- **category_constraints** *(optional)*: If non-empty, keeps only paths that contain these categories.

#### Returns

`get_paths(...)` returns a 3-tuple:

```python
(result, aux_graphs, knowledge_graph)
```

(Exact structures depend on your configured backend and downstream expectations.)

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

## License

Add your license text or a link here.
