# Pathfinder Neighbor-Ranking Model Training (XGBoost)

This script trains an **XGBoost learning-to-rank model** (`rank:pairwise`) to **rank 1-hop neighbors of a CURIE** in a knowledge graph using features collected from a PloverDB-backed KG plus local SQLite resources (node degree, NGD).

---

## Quickstart

### Run (recommended: background with logs)

```bash
nohup env PYTHONPATH=src python build_model/training/training.py \
  --kg-version "2.10.2" \
  --plover-url "https://kg2cploverdb.ci.transltr.io" \
  > output.log 2>&1 &
```

---

## What gets trained?

- **Model type**: XGBoost Learning-to-Rank (`objective=rank:pairwise`)
- **Output file**: `pathfinder_xgboost_model_kg_<KG_VERSION>`

Hyperparameters are currently hard-coded in `train()` and were taken from the last hyperparameter tuning log.

---

## Expected File

This script expects certain JSON file to exist locally:

### DrugBank-aligned dataset (required)

- `./build_model/data/DrugBank_aligned_with_KG2.json`

---

## External Dependencies

### Install dependencies

```bash
pip install -r requirements.txt
```

---

## Downloaded Databases (SSH required)

Before training, the script downloads 3 SQLite DB files for the given KG version into `--out-dir`:

- Node degree DB: `kg2c_v1.0_KG<kg_version>.sqlite`
- Node synonymizer DB: `node_synonymizer_v1.0_KG<kg_version>.sqlite`
- CURIE NGD DB: `curie_ngd_v1.0_KG<kg_version>.sqlite`

By default it downloads from:

- Host: `arax-databases.rtx.ai`
- Username: `rtxconfig`
- Port: `22`
- Remote paths (pattern):
  - `~/KG<kg_version>/<dbname>`

---

## CLI Arguments

### Required
- `--kg-version VERSION`  
  Knowledge graph version, must match `X.Y.Z` (e.g., `2.10.2`)

- `--plover-url URL`  
  PloverDB base URL used by the data collector

### Optional (DB download settings)
- `--db-host HOST` (default: `arax-databases.rtx.ai`)
- `--db-username USER` (default: `rtxconfig`)
- `--db-port PORT` (default: `22`)
- `--ssh-key PATH` (default: none; uses SSH agent/default keys)
- `--ssh-password PASSWORD` (default: none; can also use `SSH_PASSWORD` env var)
- `--out-dir DIR` (default: `.`)


---