"""
Resolve free-text biomedical terms to CURIEs with the Translator Name
Resolver (POST /lookup, https://name-lookup.transltr.io/docs).

The service's own top hit is often wrong for short or exact terms: "KIT"
comes back as human first but "copper atom" ranks strontium above copper,
and "TOR signaling" returns non-human proteins. So each term fetches a wider
candidate list and is picked locally:

  1. drop candidates tied to a non-human taxon (untaxed concepts such as
     cells, processes and chemicals are kept)
  2. prefer an exact (case-insensitive) label match
  3. then an exact synonym match
  4. otherwise leave curie empty and report the highest-scoring remaining
     candidate as a guess

A limit of 200 is needed: the exact match for "cGMP" (CHEBI:16356) ranks
95th. Some GO processes ("DNA repair", GO:0006281) are in the index but the
search never returns them, so they end up in the review list.

Resolved CURIEs are added to training_centers.json, the list of training
centers that fetch_top_neighbors.py reads; CURIEs already there are left
alone. Unresolved terms are only reported, with the best guess, so they can
be fixed in MANUAL and run again.

Usage:
    python lookup_curies.py imatinib "chronic myeloid leukemia"
    python lookup_curies.py -i terms.txt         # one term per line
    python lookup_curies.py -i terms.txt --dry-run   # resolve, change nothing
    python lookup_curies.py --builtin            # the original TERMS + PAIRS

Then run fetch_top_neighbors.py, strip_for_grading.py and
grade_top_neighbors.py; each skips CURIEs it has already done.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
URL = "https://name-lookup.transltr.io/lookup"
NODENORM = "https://nodenorm.transltr.io/get_normalized_nodes"
HUMAN = "NCBITaxon:9606"

TERMS = """
KIT
mast cell
TOP2B
cardiomyocyte
ADRB2
bronchoconstriction
HLA-B
HLA-B*57:01
HLA-B*15:02
SLCO1B1
HMGCR
MT-RNR1
m.1555A>G
cochlear hair cell
CRBN
IKZF1
IKZF3
SALL4
PDE5A
cGMP
hair follicle
SULT1A1
CYP2C19
CYP2C19*2
P2RY12
VKORC1
CYP2C9
HLA-B*58:01
AQP2
kidney collecting duct
HBG1
HBG2
HBB
NFE2L2
KEAP1
TUBB
NLRP3
neutrophil
CYP3A4
tacrolimus
DRD2
basal ganglia
influenza
mitochondrion
copper atom
ATP7B
PDCD1
CD274
T cell
mitochondrial translation
cholesterol biosynthetic process
skeletal muscle tissue
mitochondrial electron transport, NADH to ubiquinone
gluconeogenesis
myeloid cell differentiation
PML::RARA fusion
optic nerve
retinal ganglion cell
bone resorption
mandible
osteoclast
DNA repair
ERCC1
endometrium
ESR1
neural tube closure
histone deacetylation
neural tube
TOR signaling
MTOR
TSC2
blood coagulation
vitamin K metabolic process
"""


# Drug–disease pairs (tab-separated). Both sides are resolved like TERMS.
PAIRS = """
imatinib	asthma
doxorubicin	heart failure
propranolol	asthma
abacavir	drug hypersensitivity syndrome
carbamazepine	Stevens-Johnson syndrome
simvastatin	myopathy
gentamicin	sensorineural hearing loss
thalidomide	multiple myeloma
thalidomide	phocomelia
sildenafil	pulmonary arterial hypertension
minoxidil	androgenetic alopecia
clopidogrel	coronary artery in-stent thrombosis
warfarin	hemorrhage
allopurinol	Stevens-Johnson syndrome
lithium carbonate	nephrogenic diabetes insipidus
hydroxyurea	sickle cell disease
dimethyl fumarate	multiple sclerosis
colchicine	gout
hyperforin	kidney transplant rejection
metoclopramide	tardive dyskinesia
aspirin	Reye syndrome
penicillamine	Wilson disease
pembrolizumab	melanoma
simvastatin	rhabdomyolysis
metformin	lactic acidosis
all-trans retinoic acid	acute promyelocytic leukemia
ethambutol	optic neuropathy
bisphosphonate	osteonecrosis of the jaw
cisplatin	cervical cancer
tamoxifen	endometrial carcinoma
valproic acid	neural tube defect
sirolimus	lymphangioleiomyomatosis
"""

# Hand-checked CURIEs for terms the search cannot resolve or resolves wrongly.
# Each one was confirmed with /reverse_lookup or NodeNorm. A None value means
# nothing in the Translator ID space represents the term itself.
MANUAL = {
    # GO processes: indexed, but /lookup never returns them
    "mitochondrial translation": "GO:0032543",
    "cholesterol biosynthetic process": "GO:0006695",
    "mitochondrial electron transport, NADH to ubiquinone": "GO:0006120",
    "myeloid cell differentiation": "GO:0030099",
    "DNA repair": "GO:0006281",
    "neural tube closure": "GO:0001843",
    "TOR signaling": "GO:0031929",
    "blood coagulation": "GO:0007596",
    "vitamin K metabolic process": "GO:0042373",
    # GO:0016575 histone deacetylation is obsolete; the closest live parent
    "histone deacetylation": "GO:0006476",
    # auto match was a disease / a MESH class instead of the process / organelle
    "bone resorption": "GO:0045453",
    "mitochondrion": "GO:0005739",
    # HLA alleles: only the MESH antigen concepts exist
    "HLA-B*57:01": "MESH:C484830",
    "HLA-B*15:02": "MESH:C483536",
    "HLA-B*58:01": "MESH:C500126",
    "PML::RARA fusion": "UniProtKB:Q96S41",
    "coronary artery in-stent thrombosis": "UMLS:C1719989",
    "all-trans retinoic acid": "CHEBI:15367",
    # two parent cliques are named "gentamicin"; only the PubChem one has
    # edges in the Retriever KG (CHEBI:17833 has none)
    "gentamicin": "PUBCHEM.COMPOUND:3467",
    # star allele / mtDNA variant: no concept for the variant itself
    "CYP2C19*2": None,
    "m.1555A>G": None,
}


def lookup(term, limit=200, retries=3):
    params = {"string": term, "autocomplete": "false", "limit": limit}
    for attempt in range(retries):
        try:
            r = requests.post(URL, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def pick(term, candidates):
    """Return (best_candidate, match_rule) or (None, 'none')."""
    usable = [c for c in candidates if not c.get("taxa") or HUMAN in c["taxa"]]
    t = term.casefold()
    for c in usable:
        if (c.get("label") or "").casefold() == t:
            return c, "label"
    for c in usable:
        if any(s.casefold() == t for s in c.get("synonyms", [])):
            return c, "synonym"
    if usable:
        return usable[0], "fallback"
    return None, "none"


def normalize(curies):
    """
    Map CURIEs to NodeNorm's canonical id, matching the Retriever KG: gene and
    protein are conflated, drugs and chemicals are not. With drug_chemical
    conflation, imatinib becomes the mesylate salt CHEBI:31690, which has no
    edges in the KG; the parent CHEBI:45783 has thousands.
    """
    curies = sorted({c for c in curies if c})
    r = requests.post(NODENORM, json={"curies": curies, "conflate": True,
                                      "drug_chemical_conflate": False}, timeout=60)
    r.raise_for_status()
    out = {}
    for c, v in r.json().items():
        if v:
            out[c] = (v["id"]["identifier"], v["id"].get("label"), v["type"][0])
    return out


def unconflate(results):
    """
    Name lookup is built on drug/chemical-conflated cliques, so a drug name
    can come back as its salt or brand (imatinib -> CHEBI:31690 imatinib
    methanesulfonate). The Retriever KG is not conflated that way, and the
    salt has no edges there. When the chosen label differs from the term,
    look inside the conflated clique for a sub-clique named exactly like the
    term (imatinib -> CHEBI:45783) and use that instead.
    """
    todo = [r for r in results if r["curie"] and r["match"] != "manual"
            and (r["label"] or "").casefold() != r["term"].casefold()]
    for r in todo:
        conflated = requests.post(NODENORM, json={
            "curies": [r["curie"]], "conflate": True,
            "drug_chemical_conflate": True}, timeout=60).json().get(r["curie"])
        if not conflated:
            continue
        equivalents = [e["identifier"] for e in conflated["equivalent_identifiers"]]
        split = requests.post(NODENORM, json={
            "curies": equivalents, "conflate": True,
            "drug_chemical_conflate": False}, timeout=60).json()
        for v in split.values():
            if v and (v["id"].get("label") or "").casefold() == r["term"].casefold():
                print(f"  {r['term']}: {r['curie']} ({r['label']}) -> "
                      f"{v['id']['identifier']} ({v['id']['label']})")
                r["curie"], r["label"], r["type"] = (
                    v["id"]["identifier"], v["id"]["label"], v["type"][0])
                break


def resolve(terms):
    results = []
    for term in terms:
        if term in MANUAL:
            results.append({"term": term, "curie": MANUAL[term], "guess": None,
                            "label": None, "type": None,
                            "match": "manual" if MANUAL[term] else "none"})
            print(f"{term:55s} {MANUAL[term] or '-':25s} manual")
            continue
        try:
            candidates = lookup(term)
        except requests.RequestException as e:
            print(f"  ! {term}: {e}", file=sys.stderr)
            results.append({"term": term, "curie": None, "guess": None,
                            "label": None, "type": None, "match": "error"})
            continue
        best, rule = pick(term, candidates)
        exact = rule in ("label", "synonym")
        results.append({
            "term": term,
            "curie": best["curie"] if exact else None,
            "guess": best["curie"] if best and not exact else None,
            "label": best.get("label") if best else None,
            "type": best["types"][0] if best and best.get("types") else None,
            "match": rule,
        })
        print(f"{term:55s} {best['curie'] if best else '-':25s} {rule}")

    # Replace every resolved CURIE with its canonical form.
    norm = normalize(r["curie"] for r in results)
    for r in results:
        if r["curie"] in norm:
            r["curie"], r["label"], r["type"] = norm[r["curie"]]
        elif r["curie"]:
            r["type"] = r["type"] or "not in NodeNorm"
    unconflate(results)
    return results


def add_to_centers(curies, path):
    """Merge curies into the JSON list at path; returns the ones that were new."""
    path = Path(path)
    existing = json.loads(path.read_text()) if path.exists() else []
    new = sorted(set(curies) - set(existing))
    if new:
        path.write_text(json.dumps(sorted(set(existing) | set(new)), indent=2))
    return new


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("terms", nargs="*", help="terms to resolve")
    ap.add_argument("-i", "--input", help="text file, one term per line")
    ap.add_argument("--builtin", action="store_true",
                    help="resolve the original TERMS and PAIRS lists")
    ap.add_argument("--centers", default=str(HERE / "training_centers.json"),
                    help="JSON list of CURIEs to add to (default: training_centers.json)")
    ap.add_argument("--dry-run", action="store_true",
                    help="resolve and report, but do not change the centers file")
    args = ap.parse_args()

    terms = list(args.terms)
    if args.input:
        terms += Path(args.input).read_text().splitlines()
    if args.builtin:
        terms += TERMS.splitlines()
        terms += [t for line in PAIRS.splitlines() for t in line.split("\t")]
    terms = list(dict.fromkeys(t.strip() for t in terms if t.strip()))
    if not terms:
        ap.error("give terms, -i FILE or --builtin")

    results = resolve(terms)
    resolved = {r["curie"] for r in results if r["curie"]}
    unresolved = [r for r in results if not r["curie"]]

    print(f"\n{len(results)} terms, {len(resolved)} distinct CURIEs resolved")
    for r in unresolved:
        print(f"  unresolved: {r['term']} (guess: {r['guess'] or '-'})")
    if args.dry_run:
        print("dry run: centers file not changed")
        return
    new = add_to_centers(resolved, args.centers)
    print(f"{len(new)} new CURIEs added to {args.centers}, "
          f"{len(resolved) - len(new)} were already there")
    for curie in new:
        print(f"  + {curie}")


if __name__ == "__main__":
    main()
