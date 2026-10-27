# Neighbor ranker trained on LLM grades

Pathfinder prunes each expansion step to the neighbors an XGBoost ranker scores
highest (`MLRepo.get_edges`). This directory trains that ranker on relevance
grades from Claude Sonnet 5 instead of DrugBank-derived labels.

The model's input is unchanged: the same 615-length feature vector MLRepo
builds, so the trained model drops into `src/pathfinder/resources` and
Pathfinder runs without code changes.

## Pipeline

```
lookup_curies.py ─┐
                  ├─> training_centers.json
collect_ngd_rich_nodes.py ─┘
        │
        ▼
fetch_top_neighbors.py   ──> top_neighbors/          top 50 neighbors + features
        │
        ▼
strip_for_grading.py     ──> neighbors_for_grading/  id, name, category, predicates only
        │
        ▼
grade_top_neighbors.py   ──> graded_neighbors/       grade 0-4 + confidence per neighbor
        │
        ▼
train_llm_ranker.py      ──> models/ + src/pathfinder/resources/pathfinder_xgboost_model_kg_<version>
```

Every step skips work it has already done, so adding centers and re-running
the whole chain only processes the new ones.

Run everything from this directory with the repo's `src` on the path:

```bash
cd build_model/prompt_ranking
pip install -r requirements.txt
export PYTHONPATH=../../src
```

The NGD and degree databases are expected in the repo root
(`curie_ngd_v1.0_tier0-<kg>.sqlite`, `tier0-info-for-overlay_v1.0_tier0-<kg>.sqlite`);
`build_model/db_build` builds and downloads them.

## 1. Choose training centers — `training_centers.json`

A sorted JSON list of CURIEs. Each one becomes one ranking group: its top 50
neighbors are graded and ranked against each other. Two scripts add to it, and
neither removes anything already there:

- **`lookup_curies.py`**: resolves term names (drugs, diseases, genes,
  processes) with the Translator Name Resolver and NodeNorm. It prefers exact
  human matches, uses parent drugs instead of salt forms, and applies manual
  fixes from its `MANUAL` table. Unresolved terms are reported with a guess.
  ```bash
  python lookup_curies.py imatinib "chronic myeloid leukemia"
  python lookup_curies.py -i new_terms.txt --dry-run
  python lookup_curies.py --builtin      # the original 133 terms
  ```
- **`collect_ngd_rich_nodes.py`**: takes every node in the knowledge graphs of
  `pathfinder_results/*.json` and keeps the ones with more than `--min-ngd`
  (default 50) neighbor NGD values in the NGD database.

Current list: 1,765 CURIEs. 1,678 came from `pathfinder_results` and 87 from
the original term list; another 44 terms resolved to nodes already found there.
Four CURIEs have no KG neighbors, so 1,761 have training data.

## 2. Fetch neighbors — `fetch_top_neighbors.py`

For each center, gets its neighbors from the Retriever and scores them with
`MLRepo.get_edges`, the same code Pathfinder prunes with, and saves the top 50
to `top_neighbors/<curie>.json`. Each neighbor keeps the raw inputs of the
feature vector (category, predicates with counts, NGD, PMIDs, degree) plus the
fetching model's rank and score, so training needs no further KG calls.

```bash
python fetch_top_neighbors.py                   # all of training_centers.json
python fetch_top_neighbors.py --model PATH      # select neighbors with a specific model
```

By default the neighbors are selected by whichever model is installed in
`src/pathfinder/resources`. The current files were fetched with the original
DrugBank-trained model. Now that the LLM model is installed, pass `--model`
with the DrugBank model backup if new centers should be selected the same way.

## 3. Hide the ranking — `strip_for_grading.py`

Copies each file to `neighbors_for_grading/` with only id, name, category and
predicate names, sorted by id. Rank, score, weights, degree, NGD, PMIDs and
edge counts are removed so the grader cannot be biased by the current model or
by how well studied a node is.

## 4. Grade — `grade_top_neighbors.py`

Sends each center with its 50 neighbors to `claude-sonnet-5` in one request
and writes `graded_neighbors/<curie>.json`. The criterion is
`GRADING_CRITERION` in the script. In short:

| Grade | Meaning |
|---|---|
| 0 | Floor: cannot be a mechanistic waypoint (relabeling of the center, hub, broad class, bare association) |
| 1 | Weak: a specific entity with a genuine but thin or peripheral tie |
| 2 | Possible: the right kind of entity, but the step is vague or indirect |
| 3 | Strong: a specific participant (substrate, effector, receptor, site of action), not certainly central |
| 4 | Core mechanism: e.g. the direct target or the pathway acted on; rare |

The criterion asks the grader to judge what a node is biologically, not how
famous it is, and to grade each neighbor as a general waypoint, since no
destination is given.

Each neighbor also gets a `floor_reason`, a `mechanism`, a `confidence`
(high, medium or low) and a one-sentence `rationale`. The response is
constrained to a JSON schema. A neighbor the model leaves out is saved as grade 0
with the rationale "not returned by the model", and training drops it.

```bash
export ANTHROPIC_API_KEY=...
python grade_top_neighbors.py --limit 2         # try a couple first
python grade_top_neighbors.py --workers 8
```

Cost is about $0.10 per center (1,761 centers cost about $180). Requests time
out after 5 minutes without data and are retried. Failures are listed in
`graded_neighbors/_failed.json`, and re-running grades only the missing files.

## 5. Train — `train_llm_ranker.py`

Joins `graded_neighbors/` (labels) with `top_neighbors/` (features) and trains
an XGBoost `rank:pairwise` model with the same parameters as the old
`training.py`: eta 0.1, max_depth 15, subsample 0.91, colsample_bytree 0.84,
gamma 0.1, 500 rounds.

- **Features**: built with MLRepo's own `get_np_array_features` /
  `get_concatenate_features` and resource files: NGD, PMIDs, neighbor category
  one-hot (154), predicates with ancestors (243), center category one-hot
  (154), degree by category (62) = 615. `degree_by_category` comes from the
  local degree database.
- **Label**: `0` for grade 0, otherwise `grade + 0.25` (high confidence), `grade`
  (medium) or `grade − 0.25` (low). Confidence only breaks ties within a grade.
- **Groups**: one per center.
- **Validation**: 20% of centers are held out. The report gives NDCG@10/30/all
  for the new model, the model that fetched the neighbors, and random order.
  Then the model is trained on all centers.

```bash
python train_llm_ranker.py                # validate, train, install
python train_llm_ranker.py --no-install   # leave src/pathfinder/resources alone
```

Outputs:
- `models/pathfinder_xgboost_model_llm_kg_<version>`: the model
- `models/training_report.json`: data size, parameters, validation scores
- `src/pathfinder/resources/pathfinder_xgboost_model_kg_<version>`: the
  installed model. The previous one is first copied to `….bak-<timestamp>`.

## New KG version — `build_feature_resources.py`

The feature layout comes from four files in `src/pathfinder/resources`:
`sorted_category_list.pkl`, `edge_category_to_idx.pkl`,
`ancestors_by_indices.pkl` and `node_degree_category_by_indices.pkl`. Rebuild
them for a new KG or biolink version:

```bash
python build_feature_resources.py --kg-version 20260928 --out-dir /tmp/check   # compare first
python build_feature_resources.py --kg-version 20260928                          # write to resources
```

It reports each file as unchanged or CHANGED. If any file changed, the vector
layout changed: re-fetch neighbors with the new databases and retrain before
using the model. The `KG_VERSION` in `train_llm_ranker.py` and the database
defaults in `fetch_top_neighbors.py` also need updating.

## Results (KG 20260621)

| Model | Tests passed (of 79) | NDCG@10 on held-out centers |
|---|---|---|
| DrugBank labels (previous) | 32 | 0.48 |
| LLM grades, 127 centers | 30 | 0.65 |
| LLM grades, 1,761 centers | **37** | **0.73** |

NDCG is the mean over 5 random splits of 352 held-out centers, scored against
the LLM grades.

## Data not in git

`top_neighbors/`, `neighbors_for_grading/`, `graded_neighbors/`,
`pathfinder_results/` and the model copy in `models/` are ignored by git and
backed up separately. Without them, rebuilding the training data means re-running
steps 2–4, including the grading cost.
