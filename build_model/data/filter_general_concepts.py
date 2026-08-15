#!/usr/bin/env python3
"""Strip RTX-KG2 "general concept" nodes out of DrugBank_aligned_with_KG2.json.

general_concepts.json (https://github.com/RTXteam/RTX ARAX KnowledgeSources)
lists curies, name synonyms, and name regex patterns that are considered too
generic to be useful knowledge-graph nodes (e.g. "epidemiology", "congenital").

This walks DrugBank_aligned_with_KG2.json and, wherever it finds a curie-keyed
node map (a dict whose values are themselves dicts with a "name" field --
this covers the top-level drug entries as well as nested maps such as
indication_NER_aligned and mechanistic_intermediate_nodes), drops any entry
whose curie or name is flagged as a general concept.

A node is dropped when any of the following hold:
  - its curie is in general_concepts["curies"] (exact match)
  - its lowercased name is in general_concepts["synonyms"] (lowercased)
  - its name matches (case-insensitively) any regex in general_concepts["patterns"]
"""
import argparse
import json
import re
from pathlib import Path


def load_general_concepts(path):
    with open(path) as f:
        data = json.load(f)
    curies = set(data.get("curies", []))
    synonyms = set(s.lower() for s in data.get("synonyms", []))
    patterns = [re.compile(p, re.IGNORECASE) for p in data.get("patterns", [])]
    return curies, synonyms, patterns


def is_general_concept(curie, name, curies, synonyms, patterns):
    if curie in curies:
        return True
    name = name or ""
    if name.lower() in synonyms:
        return True
    return any(p.search(name) for p in patterns)


def prune(obj, curies, synonyms, patterns, stats):
    if isinstance(obj, dict):
        if obj and all(isinstance(v, dict) for v in obj.values()):
            for curie in list(obj.keys()):
                info = obj[curie]
                if "name" in info and is_general_concept(curie, info.get("name"), curies, synonyms, patterns):
                    del obj[curie]
                    stats["removed"] += 1
        for value in obj.values():
            prune(value, curies, synonyms, patterns, stats)
    elif isinstance(obj, list):
        for item in obj:
            prune(item, curies, synonyms, patterns, stats)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--drugbank", default=str(Path(__file__).with_name("DrugBank_aligned_with_KG2.json")),
                         help="Path to DrugBank_aligned_with_KG2.json")
    parser.add_argument("--general-concepts", default=str(Path(__file__).resolve().parents[2] / "general_concepts.json"),
                         help="Path to general_concepts.json")
    parser.add_argument("--output", default=None,
                         help="Where to write the filtered file (default: <drugbank>.filtered.json)")
    parser.add_argument("--in-place", action="store_true",
                         help="Overwrite --drugbank instead of writing a separate file")
    args = parser.parse_args()

    curies, synonyms, patterns = load_general_concepts(args.general_concepts)

    with open(args.drugbank) as f:
        data = json.load(f)

    stats = {"removed": 0}
    prune(data, curies, synonyms, patterns, stats)

    if args.in_place:
        out_path = Path(args.drugbank)
    elif args.output:
        out_path = Path(args.output)
    else:
        out_path = Path(args.drugbank).with_suffix(".filtered.json")

    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    with open(tmp_path, "w") as f:
        json.dump(data, f)
    tmp_path.replace(out_path)

    print(f"Removed {stats['removed']} general-concept entries; wrote {out_path}")


if __name__ == "__main__":
    main()