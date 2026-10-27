"""
Copy top_neighbors/*.json into neighbors_for_grading/ with everything that
could bias the LLM grader removed.

Kept per center:    curie, name, category, terms
Kept per neighbor:  id, name, category, predicates (names only, no counts)
Dropped:            rank, score, weight, weight_bar, degree, ngd, pmids,
                    n_neighbors, and the per-predicate edge counts

Neighbors are written in id order so the XGBoost ranking cannot leak through
the ordering. Files already in neighbors_for_grading/ are left untouched.

Usage:
    python strip_for_grading.py
"""

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def strip(data):
    return {
        "curie": data["curie"],
        "name": data["name"],
        "category": data["category"],
        "terms": data.get("terms", []),
        "neighbors": sorted(
            ({"id": n["id"], "name": n["name"], "category": n["category"],
              "predicates": sorted(n["predicates"])} for n in data["neighbors"]),
            key=lambda n: n["id"]),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--in-dir", default=str(HERE / "top_neighbors"))
    ap.add_argument("--out-dir", default=str(HERE / "neighbors_for_grading"))
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = skipped = 0
    for path in sorted(Path(args.in_dir).glob("*.json")):
        target = out_dir / path.name
        if target.exists():
            skipped += 1
            continue
        target.write_text(json.dumps(strip(json.loads(path.read_text())), indent=2))
        written += 1
    print(f"{written} written, {skipped} already present -> {out_dir}")


if __name__ == "__main__":
    main()
