"""
Collect every node in the knowledge graphs of pathfinder_results/*.json and
keep the ones whose entry in the NGD database lists more than --min-ngd
neighbor NGD values.

The kept nodes are added to training_centers.json (a sorted list of CURIEs);
CURIEs already there, such as ones added by lookup_curies.py, stay.

Usage:
    python collect_ngd_rich_nodes.py
    python collect_ngd_rich_nodes.py --min-ngd 50 --dry-run
"""

import argparse
import ast
import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def collect_nodes(results_dir):
    nodes = set()
    files = sorted(Path(results_dir).glob("*.json"))
    for path in files:
        kg = json.loads(path.read_text()).get("message", {}).get("knowledge_graph") or {}
        nodes.update((kg.get("nodes") or {}).keys())
    return nodes, len(files)


def ngd_counts(db_path, curies, chunk_size=900):
    """curie -> number of neighbor NGD values stored for it."""
    counts = {}
    curies = sorted(curies)
    with sqlite3.connect(db_path) as conn:
        for i in range(0, len(curies), chunk_size):
            chunk = curies[i:i + chunk_size]
            rows = conn.execute(
                f"SELECT curie, ngd FROM curie_ngd WHERE curie IN ({','.join('?' * len(chunk))})",
                chunk)
            for curie, ngd in rows:
                counts[curie] = len(ast.literal_eval(ngd))
    return counts


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--results-dir", default=str(HERE / "pathfinder_results"))
    ap.add_argument("--ngd-db", default=str(ROOT / "curie_ngd_v1.0_tier0-20260621.sqlite"))
    ap.add_argument("--min-ngd", type=int, default=50,
                    help="keep nodes with MORE than this many NGD values")
    ap.add_argument("--centers", default=str(HERE / "training_centers.json"),
                    help="JSON list of CURIEs to add to")
    ap.add_argument("--dry-run", action="store_true",
                    help="report counts, but do not change the centers file")
    args = ap.parse_args()

    nodes, n_files = collect_nodes(args.results_dir)
    counts = ngd_counts(args.ngd_db, nodes)
    kept = sorted(c for c, n in counts.items() if n > args.min_ngd)

    print(f"{n_files} result files, {len(nodes)} distinct nodes")
    print(f"{len(counts)} found in the NGD database, "
          f"{len(nodes) - len(counts)} not found")
    print(f"{len(kept)} have more than {args.min_ngd} NGD values")

    centers = Path(args.centers)
    existing = json.loads(centers.read_text()) if centers.exists() else []
    new = sorted(set(kept) - set(existing))
    print(f"{len(new)} not yet in {centers.name} ({len(existing)} there now)")
    if args.dry_run:
        print("dry run: centers file not changed")
        return
    centers.write_text(json.dumps(sorted(set(existing) | set(kept)), indent=2))
    print(f"{centers.name} now has {len(existing) + len(new)} CURIEs")


if __name__ == "__main__":
    main()
