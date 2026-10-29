"""
Rebuild the four feature-layout files MLRepo and train_llm_ranker.py use to
turn a neighbor into its 615-length feature vector:

  sorted_category_list.pkl            node categories (Node Synonymizer)
  edge_category_to_idx.pkl            biolink predicates under related_to
  ancestors_by_indices.pkl            predicate index -> ancestor indices
  node_degree_category_by_indices.pkl degree categories in the degree sqlite

Run this when moving to a new KG or biolink version. If any file changes, the
vector layout changes too, so retrain with train_llm_ranker.py before using
the model.

Needs node-synonymizer and biolink-helper-pkg (pip install
node-synonymizer==0.1.1 biolink-helper-pkg==1.0.0).

Usage:
    PYTHONPATH=../../src python build_feature_resources.py --kg-version 20260621
    PYTHONPATH=../../src python build_feature_resources.py --kg-version 20260928 --out-dir /tmp/check
"""

import argparse
import logging
import pickle
from pathlib import Path

from biolink_helper_pkg import BiolinkHelper
from node_synonymizer import NodeSynonymizer

from pathfinder.core.repo.NodeDegreeRepo import NodeDegreeRepo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BIOLINK_VERSION = "4.2.5"


def degree_category_to_idx(degree_db):
    categories = sorted(NodeDegreeRepo(str(degree_db)).get_degree_categories())
    return {c: i for i, c in enumerate(categories)}


def edge_category_to_idx(biolink):
    predicates = sorted(biolink.get_descendants("biolink:related_to"))
    return {p: i for i, p in enumerate(predicates)}


def ancestors_by_indices(biolink, edge_idx):
    # sorted: biolink returns ancestors in no fixed order, and the order does
    # not matter to the features (each index just sets a 1)
    return {idx: sorted(edge_idx[a] for a in biolink.get_ancestors(predicate) if a in edge_idx)
            for predicate, idx in edge_idx.items()}


def same_layout(old, new):
    """Equal, ignoring the order inside ancestor lists."""
    if isinstance(old, dict) and isinstance(new, dict) and old.keys() == new.keys():
        return all(sorted(old[k]) == sorted(new[k]) if isinstance(old[k], list) else old[k] == new[k]
                   for k in old)
    return old == new


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--kg-version", required=True, help="e.g. 20260621")
    ap.add_argument("--degree-db", help="default: tier0-info-for-overlay_v1.0_tier0-<kg>.sqlite "
                                        "in the repo root")
    ap.add_argument("--biolink-version", default=BIOLINK_VERSION)
    ap.add_argument("--biolink-cache", default=str(ROOT / "biolink"))
    ap.add_argument("--out-dir", default=str(ROOT / "src/pathfinder/resources"))
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    degree_db = Path(args.degree_db or ROOT / f"tier0-info-for-overlay_v1.0_tier0-{args.kg_version}.sqlite")
    Path(args.biolink_cache).mkdir(parents=True, exist_ok=True)
    biolink = BiolinkHelper(args.biolink_version, args.biolink_cache)

    edge_idx = edge_category_to_idx(biolink)
    resources = {
        "sorted_category_list.pkl": sorted(NodeSynonymizer().get_distinct_category_list()),
        "edge_category_to_idx.pkl": edge_idx,
        "ancestors_by_indices.pkl": ancestors_by_indices(biolink, edge_idx),
        "node_degree_category_by_indices.pkl": degree_category_to_idx(degree_db),
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, value in resources.items():
        path = out_dir / name
        if not path.exists():
            status = "new"
        else:
            status = "unchanged" if same_layout(pickle.loads(path.read_bytes()), value) else "CHANGED"
        with open(path, "wb") as f:
            pickle.dump(value, f)
        logging.info(f"{name}: {len(value)} entries, {status}")
    logging.info(f"feature length = 2 + 2 * {len(resources['sorted_category_list.pkl'])} "
                 f"+ {len(edge_idx)} + {len(resources['node_degree_category_by_indices.pkl'])}")


if __name__ == "__main__":
    main()
