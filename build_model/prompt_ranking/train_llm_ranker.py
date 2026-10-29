"""
Train the Pathfinder XGBoost neighbor ranker on LLM grades instead of
DrugBank labels.

Inputs (all local; no Anthropic, Retriever or Gandalf calls):
  top_neighbors/      features per neighbor: category, predicates, ngd, pmids
  graded_neighbors/   labels per neighbor: grade 0-4 and confidence
  degree sqlite       degree_by_category per neighbor (scalar degree is all
                      top_neighbors kept; MLRepo uses the per-category form)

Features are built with the same functions and resource files MLRepo uses
(get_np_array_features / get_concatenate_features, sorted_category_list,
edge_category_to_idx, ancestors_by_indices, node_degree_category_by_indices),
so the model drops into MLRepo unchanged. Like training.py, only the forward
(center -> neighbor) vector is used for training; MLRepo applies the same
model to the inverse vector at prediction time.

Label:
    grade 0   -> 0.0
    grade > 0 -> grade + {high: +0.25, medium: 0, low: -0.25}
The +-0.25 never crosses a grade boundary, so confidence only breaks ties
inside a grade. Neighbors the LLM never returned are dropped, not labeled 0.

Usage:
    python train_llm_ranker.py                # validate, train on all, install
    python train_llm_ranker.py --no-install   # leave src/pathfinder/resources alone
"""

import argparse
import json
import logging
import pickle
import shutil
from datetime import datetime
from importlib.resources import files as resource_files
from pathlib import Path

import numpy as np
import xgboost as xgb

from pathfinder.core.feature_extractor import (get_category, get_concatenate_features,
                                               get_np_array_features)
from pathfinder.core.repo.NodeDegreeRepo import NodeDegreeRepo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KG_VERSION = "20260621"
RESOURCE_MODEL = ROOT / "src/pathfinder/resources" / f"pathfinder_xgboost_model_kg_{KG_VERSION}"

CONF_OFFSET = {"high": 0.25, "medium": 0.0, "low": -0.25}
NOT_RETURNED = "not returned by the model"

# Same parameters as training.py's train()
PARAMS = {
    "objective": "rank:pairwise",
    "eval_metric": "ndcg",
    "eta": 0.1,
    "max_depth": 15,
    "subsample": 0.91,
    "colsample_bytree": 0.84,
    "min_child_weight": 1,
    "gamma": 0.1,
}
NUM_BOOST_ROUND = 500


def load_resources():
    """Exactly what MLRepo.load_data loads."""
    pkg = resource_files("pathfinder.resources")

    def load(name):
        with pkg.joinpath(name).open("rb") as f:
            return pickle.load(f)

    sorted_category_list = load("sorted_category_list.pkl")
    return {
        "degree_category_to_idx": load("node_degree_category_by_indices.pkl"),
        "category_to_idx": {c: i for i, c in enumerate(sorted_category_list)},
        "edge_category_to_idx": load("edge_category_to_idx.pkl"),
        "ancestors_by_indices": load("ancestors_by_indices.pkl"),
    }


def score_of(grade, confidence):
    if grade <= 0:
        return 0.0
    return grade + CONF_OFFSET.get(confidence, -0.25)


def build_dataset(top_dir, graded_dir, degree_repo, res):
    """Returns x, y, group sizes and per-row metadata, one group per center."""
    x_rows, y, group, meta = [], [], [], []
    dropped = 0
    for graded_path in sorted(Path(graded_dir).glob("*.json")):
        top_path = Path(top_dir) / graded_path.name
        graded = json.loads(graded_path.read_text())
        top = json.loads(top_path.read_text())
        features_by_id = {n["id"]: n for n in top["neighbors"]}

        center_onehot = get_category(top["category"].split(":")[-1], res["category_to_idx"])
        labeled = [g for g in graded["neighbors"] if g["rationale"] != NOT_RETURNED]
        dropped += len(graded["neighbors"]) - len(labeled)
        degrees = degree_repo.get_degrees_by_node([g["id"] for g in labeled])

        for g in labeled:
            n = features_by_id[g["id"]]
            # the same record shape get_neighbors_info builds for MLRepo
            value = {
                "ngd": n["ngd"],
                "pmids": n["pmids"],
                "category": n["category"] or "",
                "edges": n["predicates"],
                "degree_by_category": degrees.get(g["id"], {}),
            }
            parts = get_np_array_features(
                value, res["category_to_idx"], res["edge_category_to_idx"],
                center_onehot, res["ancestors_by_indices"], res["degree_category_to_idx"])
            x_rows.append(get_concatenate_features(*parts))
            y.append(score_of(g["grade"], g["confidence"]))
            meta.append({"center": graded["curie"], "id": g["id"],
                         "old_score": n["score"]})
        group.append(len(labeled))

    logging.info(f"{len(group)} centers, {len(y)} neighbors "
                 f"({dropped} dropped: not graded by the LLM)")
    return np.vstack(x_rows), np.array(y, dtype=float), np.array(group), meta


def ndcg(labels, scores, k=None):
    """NDCG with the 2^label - 1 gain XGBoost's ndcg uses."""
    order = np.argsort(-scores, kind="stable")
    ideal = np.sort(labels)[::-1]
    k = len(labels) if k is None else min(k, len(labels))
    discount = 1.0 / np.log2(np.arange(2, k + 2))
    dcg = np.sum((2 ** labels[order][:k] - 1) * discount)
    idcg = np.sum((2 ** ideal[:k] - 1) * discount)
    return dcg / idcg if idcg > 0 else None


def mean_ndcg(y, scores, group, k):
    vals, start = [], 0
    for size in group:
        v = ndcg(y[start:start + size], scores[start:start + size], k)
        if v is not None:
            vals.append(v)
        start += size
    return float(np.mean(vals))


def split_groups(group, val_fraction, seed):
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(group))
    n_val = max(1, int(round(len(group) * val_fraction)))
    return set(order[:n_val].tolist())


def take(x, y, group, meta, keep):
    xs, ys, gs, ms, start = [], [], [], [], 0
    for i, size in enumerate(group):
        if i in keep:
            xs.append(x[start:start + size])
            ys.append(y[start:start + size])
            ms.extend(meta[start:start + size])
            gs.append(size)
        start += size
    return np.vstack(xs), np.concatenate(ys), np.array(gs), ms


def fit(x, y, group):
    dtrain = xgb.DMatrix(x, label=y)
    dtrain.set_group(group)
    return xgb.train(PARAMS, dtrain, num_boost_round=NUM_BOOST_ROUND)


def validate(x, y, group, meta, val_fraction, seed):
    """
    Hold out whole centers, train on the rest, and compare the new model's
    ordering against the production model's (the score saved in
    top_neighbors) on the held-out centers.
    """
    val_idx = split_groups(group, val_fraction, seed)
    train_idx = set(range(len(group))) - val_idx
    xt, yt, gt, _ = take(x, y, group, meta, train_idx)
    xv, yv, gv, mv = take(x, y, group, meta, val_idx)

    bst = fit(xt, yt, gt)
    new_scores = bst.predict(xgb.DMatrix(xv))
    old_scores = np.array([m["old_score"] for m in mv])
    rng = np.random.default_rng(seed)
    random_scores = rng.random(len(yv))

    logging.info(f"validation: {len(gt)} train / {len(gv)} held-out centers")
    report = {}
    for k in (10, 30, None):
        name = f"ndcg@{k}" if k else "ndcg@all"
        report[name] = {
            "new_model": mean_ndcg(yv, new_scores, gv, k),
            "production_model": mean_ndcg(yv, old_scores, gv, k),
            "random": mean_ndcg(yv, random_scores, gv, k),
        }
        r = report[name]
        logging.info(f"  {name:9s} new {r['new_model']:.3f} | production "
                     f"{r['production_model']:.3f} | random {r['random']:.3f}")
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--top-dir", default=str(HERE / "top_neighbors"))
    ap.add_argument("--graded-dir", default=str(HERE / "graded_neighbors"))
    ap.add_argument("--degree-db", default=str(ROOT / f"tier0-info-for-overlay_v1.0_tier0-{KG_VERSION}.sqlite"))
    ap.add_argument("--out-dir", default=str(HERE / "models"))
    ap.add_argument("--val-fraction", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-install", action="store_true",
                    help="do not copy the model into src/pathfinder/resources")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    res = load_resources()
    x, y, group, meta = build_dataset(args.top_dir, args.graded_dir,
                                      NodeDegreeRepo(args.degree_db), res)
    logging.info(f"feature vector length {x.shape[1]}")

    report = validate(x, y, group, meta, args.val_fraction, args.seed)

    logging.info("training on all centers")
    bst = fit(x, y, group)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / f"pathfinder_xgboost_model_llm_kg_{KG_VERSION}"
    bst.save_model(str(model_path))
    (out_dir / "training_report.json").write_text(json.dumps({
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "centers": int(len(group)), "neighbors": int(len(y)),
        "feature_length": int(x.shape[1]), "params": PARAMS,
        "num_boost_round": NUM_BOOST_ROUND, "validation": report,
    }, indent=2))
    logging.info(f"model saved to {model_path}")

    if not args.no_install:
        if RESOURCE_MODEL.exists():
            backup = RESOURCE_MODEL.with_name(
                RESOURCE_MODEL.name + f".bak-{datetime.now():%Y%m%d-%H%M%S}")
            shutil.copy2(RESOURCE_MODEL, backup)
            logging.info(f"previous resource model backed up to {backup}")
        shutil.copy2(model_path, RESOURCE_MODEL)
        logging.info(f"installed as {RESOURCE_MODEL} (the file MLRepo loads)")


if __name__ == "__main__":
    main()
