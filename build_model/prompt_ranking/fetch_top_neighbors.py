"""
Save the top-N neighbors of each CURIE in training_centers.json, as ranked by the
Pathfinder XGBoost model, one JSON file per CURIE.

Neighbors come from the Retriever and are scored by MLRepo.get_edges, which
is the exact code the bidirectional expander prunes with, so the saved
neighbors are the ones that would survive pruning today. The ranking is the
same (weight + weight_bar) / 2 that MLRepo sorts by.

Each file also carries the raw features the ranker sees (predicates, ngd,
pmids, degree) so later grading does not need another KG round trip.

Usage:
    python fetch_top_neighbors.py
    python fetch_top_neighbors.py --model /path/to/xgboost_model --top 50

Files that already exist are skipped, so an interrupted run can be resumed.
"""

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

import xgboost as xgb
from tqdm import tqdm

from pathfinder.core.feature_extractor import get_neighbors_info
from pathfinder.core.repo.MLRepo import MLRepo
from pathfinder.core.repo.RetrieverRepo import RetrieverRepo
from pathfinder.core.repo.repo_factory import get_degree_repo, get_ngd_repo

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


class CachingRepo:
    """
    Remembers the last Retriever response so get_neighbors_info (for the raw
    features) and MLRepo.get_edges (for the scores) share one KG call.
    """

    def __init__(self, repo):
        self.repo = repo
        self._curie = None
        self._response = None

    def get_neighbors_with_edges(self, curie):
        if curie != self._curie:
            self._response = self.repo.get_neighbors_with_edges(curie)
            self._curie = curie
        return self._response


def load_terms(path):
    """
    curie -> the terms it came from. Accepts a JSON list of CURIEs such as
    training_centers.json (no source terms), or a TSV with term and curie
    columns as written by lookup_curies.py (unresolved terms skipped).
    """
    if str(path).endswith(".json"):
        return {curie: [] for curie in json.loads(Path(path).read_text())}
    terms_by_curie = {}
    with open(path) as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["curie"]:
                terms_by_curie.setdefault(row["curie"], []).append(row["term"])
    return terms_by_curie


def top_neighbors(ml_repo, curie, top):
    content, name, category, _ = get_neighbors_info(
        curie, ml_repo.ngd_repo, ml_repo.repo, ml_repo.degree_repo)
    if content is None:
        return None
    edges, _ = ml_repo.get_edges(curie)

    neighbors = []
    for rank, edge in enumerate(edges[:top], start=1):
        info = content[edge.target.id]
        neighbors.append({
            "rank": rank,
            "id": edge.target.id,
            "name": edge.target.name,
            "category": edge.target.category,
            "score": edge.compute_weight(),
            "weight": edge.weight,
            "weight_bar": edge.weight_bar,
            "predicates": info["edges"],
            "degree": edge.target.degree,
            "ngd": info["ngd"],
            "pmids": info["pmids"],
        })
    return {
        "curie": curie,
        "name": name,
        "category": category,
        "degree": edges[0].source.degree if edges else None,
        "n_neighbors": len(edges),
        "neighbors": neighbors,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--terms", default=str(HERE / "training_centers.json"),
                    help="a JSON list of CURIEs, or a term/curie TSV")
    ap.add_argument("--out-dir", default=str(HERE / "top_neighbors"))
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--model", help="XGBoost model file; default is the one "
                                    "packaged in pathfinder.resources")
    ap.add_argument("--retriever", default="https://retriever.ci.transltr.io/query")
    ap.add_argument("--degree-threshold", type=int, default=30000,
                    help="Retriever max_node_degree (Pathfinder.get_paths default)")
    ap.add_argument("--maturity", default="development",
                    help="sent to the Retriever as submitter arax-pathfinder@<maturity>")
    ap.add_argument("--ngd-db", default=str(ROOT / "curie_ngd_v1.0_tier0-20260621.sqlite"))
    ap.add_argument("--degree-db", default=str(ROOT / "tier0-info-for-overlay_v1.0_tier0-20260621.sqlite"))
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    degree_repo = get_degree_repo(f"sqlite:{args.degree_db}")
    ngd_repo = get_ngd_repo(f"sqlite:{args.ngd_db}")
    kg_repo = CachingRepo(RetrieverRepo(args.degree_threshold, args.retriever, degree_repo,
                                         args.maturity))
    ml_repo = MLRepo(kg_repo, degree_repo, ngd_repo)
    if args.model:
        ml_repo.bst_loaded = xgb.Booster()
        ml_repo.bst_loaded.load_model(args.model)
    logging.info(f"model: {args.model or 'packaged pathfinder_xgboost_model_kg_20260621'}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    terms_by_curie = load_terms(args.terms)

    failed, empty = {}, []
    for curie, terms in tqdm(terms_by_curie.items()):
        path = out_dir / f"{curie.replace(':', '_')}.json"
        if path.exists():
            continue
        try:
            result = top_neighbors(ml_repo, curie, args.top)
        except Exception as e:
            failed[curie] = str(e)
            logging.warning(f"{curie}: {e}")
            continue
        if result is None:
            empty.append(curie)
            continue
        result["terms"] = terms
        with open(path, "w") as f:
            json.dump(result, f, indent=2)

    logging.info(f"{len(terms_by_curie)} CURIEs -> {out_dir}; "
                 f"{len(empty)} with no neighbors: {empty}; {len(failed)} failed")
    if failed:
        with open(out_dir / "_failed.json", "w") as f:
            json.dump(failed, f, indent=2)
        sys.exit(1)


if __name__ == "__main__":
    main()
