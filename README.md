# catrax-pathfinder

`catrax-pathfinder` is a Python package for discovering and returning candidate paths between two CURIE nodes using a PloverDB endpoint and precomputed databases (NGD and node degree). It supports **SQLite** and **MySQL** backends for both the NGD and degree repositories via a simple URL prefix.

---

## Installation

```bash
pip install catrax-pathfinder
```

---

## Obtain databases

You will need a compatible curie_ngd_v1.0_KG and kg2c_v1.0_KG SQLite database for the KG version you are using.

- **Recommended**: Ask a team member for mysql urls to these databases
- **Alternative**: Ask a team member for local copies of these databases
 


## Quickstart

```python
from pathfinder.Pathfinder import Pathfinder

plover_url = "https://kg2cploverdb.ci.transltr.io"

ngd_url = "sqlite:curie_ngd_v1.0_KG2.10.2.sqlite"
degree_url = "sqlite:kg2c_v1.0_KG2.10.2.sqlite"

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
    src_pinned_node="node_1",
    dst_pinned_node="node_2",
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
    repository_name: str,
    plover_url: str,
    ngd_url: str,
    degree_url: str,
    blocked_curies: Set[str],
    blocked_synonyms: Set[str],
    logger,
)
```

#### Parameters

- **repository_name**: For now, this should always be `"MLRepo"`.
- **plover_url**: URL of the PloverDB endpoint (example: `https://kg2cploverdb.ci.transltr.io`).
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


