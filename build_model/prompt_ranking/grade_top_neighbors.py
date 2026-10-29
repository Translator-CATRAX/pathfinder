"""
Grade the neighbors in neighbors_for_grading/ with Claude Sonnet 5 and write
one graded, sorted JSON file per CURIE.

neighbors_for_grading/ holds only id, name, category and predicate names for
each neighbor, in id order: no XGBoost rank, score or weights, and no degree,
ngd or pmids, so nothing numeric can bias the grades. Every neighbor is
presented the same way and GRADING_CRITERION below decides.

Output: graded_neighbors/<curie>.json, neighbors sorted by grade (high to
low), then confidence (high, medium, low), then name.

Usage:
    export ANTHROPIC_API_KEY=...
    python grade_top_neighbors.py                 # all files, 4 in parallel
    python grade_top_neighbors.py --limit 2       # try a couple first

Existing output files are skipped, so an interrupted run can be resumed.
"""

import argparse
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic

HERE = Path(__file__).resolve().parent

MODEL = "claude-sonnet-5"
FLOOR_REASONS = ["relabeling", "hub", "broad_class", "association", "unknown", "none"]
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}

# Structured output: the response is guaranteed to be JSON matching this schema, and adaptive
# thinking (Sonnet 5's default) stays on.
GRADES_SCHEMA = {
    "type": "object",
    "properties": {
        "grades": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "grade": {"type": "integer", "enum": [0, 1, 2, 3, 4]},
                    "floor_reason": {"type": "string", "enum": FLOOR_REASONS},
                    "mechanism": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "rationale": {"type": "string"},
                },
                "required": ["id", "grade", "floor_reason", "mechanism",
                             "confidence", "rationale"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["grades"],
    "additionalProperties": False,
}

# The grading criterion, formatted with origin_name. It deliberately says
# nothing about connectivity, since none is sent to the model.
GRADING_CRITERION = """
You are grading a sample of the neighbors of one node in a biomedical
knowledge graph. Your grades train a model that prunes the frontier during a
search for mechanistic explanations, so grade each candidate on its value as
a step in such an explanation. There is no specific destination — grade for
general usefulness as a waypoint.

Each candidate line gives id, name, biolink category, and the predicate(s)
on the edge(s) linking it to {origin_name}. Edge direction is not available;
do not infer it.

Work in two steps.

STEP 1 — FLOOR SCREEN
First identify every candidate that cannot serve as a mechanistic waypoint.
These all receive grade 0. Grade 0 is a flat, intentional tie: do not rank
within it and do not try to separate a slightly less useless node from a more
useless one. Floor a candidate if any of the following holds.

  relabeling      It is a synonym, isoform, ortholog, direct subclass,
                  superclass, gene product, or other renaming of
                  {origin_name}.

  hub             It would look equally reasonable next to a few hundred
                  unrelated center nodes. "Inflammation," "apoptosis," "cell
                  death," "oxidative stress," "signal transduction," "protein
                  binding," "cancer," "gene expression," and broad common
                  metabolites like water, ATP, glucose and calcium connect to
                  nearly everything and therefore explain nearly nothing. A
                  path through one of them can link almost any two entities,
                  which is exactly the failure this model exists to prevent.

                  Judge this from what the node is, not from how widely
                  studied or broadly involved it seems. A node can take part
                  in many processes and still be the entire mechanism here.
                  A direct thrombin inhibitor's edge to thrombin is the
                  central fact about that drug no matter how many other
                  things thrombin touches. Ask what the node IS to
                  {origin_name}. Conversely, an obscure node is not good
                  just because it is narrow if its role here is vague.

  broad_class     A wide drug class, chemical role, or ontology umbrella
                  rather than a specific entity — "antineoplastic agent,"
                  "enzyme inhibitor," "organic molecule."

  association     The only link is statistical or textual: co-occurrence,
                  comorbidity, correlation, shared indication, co-mention in
                  the literature. Predicates such as related_to,
                  associated_with, correlated_with, coexists_with and
                  occurs_together_in_literature_with point this way. A weak
                  predicate alone does not floor a candidate — judge the node
                  first and use the predicate as corroboration — but when the
                  predicate is weak AND you cannot state a specific
                  biological step, floor it.

  unknown         You cannot identify the entity well enough to say what it
                  is biologically.

STEP 2 — GRADE THE REMAINDER, 1 TO 4
For everything that survived the screen, ask: can I state in one sentence a
specific biological step in which {origin_name} acts on, through, or via this
candidate? Not "these are associated," but an actual step — binds, inhibits,
is metabolized by, activates, is a substrate of, is expressed in, is released
by, accumulates in. A good waypoint also has to lead somewhere: prefer
candidates that open onto their own rich downstream biology (a receptor, an
enzyme, a cell type) over terminal descriptors.

  4  Core mechanism. I can state the specific step in one sentence and would
     be surprised to see this node missing from an account of how
     {origin_name} works — its direct target, the protein it binds, the
     pathway it acts on.

  3  Strong. A specific, plausible participant — a real substrate, product,
     downstream effector, receptor, or the cell or tissue where the action
     happens — though not certainly central, or one step off the core
     account.

  2  Possible. The right type of entity and topically apposite, but the step
     is vague or inferred from general principles rather than known. A
     specific condition this node is used for or implicated in, where the
     causal chain is real but indirect, belongs here.

  1  Weak but not floored. A specific, identifiable biological entity with
     some genuine tie to {origin_name}, where the mechanistic step is thin,
     peripheral, or an incidental downstream consequence.

Judge on what the entity IS biologically, not on how often you have seen its
name. Do not reward fame or literature volume.

Expect a large share of any basket to land at 0, and most of the remainder at
1 or 2. Grades of 4 should be rare — often one or two per basket, sometimes
none.

DIVERSITY
Where several candidates represent the same mechanism or the same branch of
this node's biology, keep the one or two best at full grade and drop the rest
by one. Give every candidate a short mechanism label and reuse the same label
across candidates on the same branch, so redundancy is visible downstream.
Use "none" for floored candidates.

CONFIDENCE
Set confidence to how sure you are of the grade itself — low when the entity
is unfamiliar to you or the call was close — so uncertain labels can be
filtered before training.

RATIONALE
For grades 1-4, one short sentence naming the specific step. For grade 0, two
to four words is enough.
"""


def build_prompt(center, basket):
    """The prompt for one center: its neighbors, one per line, then the criterion."""
    criterion = GRADING_CRITERION.format(origin_name=center["name"])
    lines = "\n".join(
        f"{n['id']} | {n['name']} | {n['category'].replace('biolink:', '')} | "
        f"{','.join(p.replace('biolink:', '') for p in n['predicates']) or 'no predicate'}"
        for n in basket)
    return f"""Center node: {center['name']} ({center['category'].replace('biolink:', '')}, id={center['id']})

Below is a sample of {len(basket)} neighbors of this node from a biomedical knowledge graph. Each line is:
id | name | category | predicate(s)

{lines}

Grade every candidate by the following criterion.

{criterion}

Return a JSON object whose "grades" array has one entry per candidate: id, grade (0-4), floor_reason (relabeling, hub, broad_class, association, unknown, or none for grades 1-4), mechanism, confidence and rationale. Include every id listed above exactly once, verbatim."""


def load_basket(path):
    data = json.loads(Path(path).read_text())
    center = {"id": data["curie"], "name": data["name"] or data["curie"],
              "category": data["category"] or ""}
    neighbors = []
    for n in data["neighbors"]:
        name = (n["name"] or n["id"]).strip()
        neighbors.append({
            "id": n["id"],
            "name": name if len(name) <= 90 else name[:90].rstrip() + "…",
            "category": n["category"] or "",
            "predicates": n["predicates"],
        })
    return data, center, neighbors


def call_model(client, center, basket):
    prompt = build_prompt(center, basket)
    with client.messages.stream(
        model=MODEL,
        max_tokens=64000,
        output_config={"format": {"type": "json_schema", "schema": GRADES_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()

    if response.stop_reason == "refusal":
        raise RuntimeError(f"refused: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("hit max_tokens before finishing")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["grades"], response.usage


def grade_file(client, path, out_dir):
    data, center, neighbors = load_basket(path)
    # Every neighbor goes to the model; none is pre-floored in code.
    records, usage = call_model(client, center, neighbors)
    valid = {n["id"] for n in neighbors}
    graded = {}
    for rec in records:
        if rec["id"] in valid and rec["id"] not in graded:
            graded[rec["id"]] = rec
    for nid in valid - set(graded):
        graded[nid] = {"id": nid, "grade": 0, "floor_reason": "unknown",
                       "mechanism": "none", "confidence": "low",
                       "rationale": "not returned by the model"}

    rows = []
    for n in neighbors:
        g = graded[n["id"]]
        rows.append({**{k: n[k] for k in ("id", "name", "category", "predicates")},
                     **{k: g[k] for k in ("grade", "floor_reason", "mechanism",
                                          "confidence", "rationale")}})
    rows.sort(key=lambda r: (-r["grade"], CONFIDENCE_ORDER.get(r["confidence"], 3),
                             r["name"].lower()))

    out = {"curie": data["curie"], "name": data["name"], "category": data["category"],
           "terms": data.get("terms", []),
           "grader": MODEL, "neighbors": rows}
    target = out_dir / path.name
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, indent=2))
    tmp.replace(target)          # never leave a half-written file behind
    return usage


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--in-dir", default=str(HERE / "neighbors_for_grading"))
    ap.add_argument("--out-dir", default=str(HERE / "graded_neighbors"))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, help="grade at most this many files")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    todo = [p for p in sorted(Path(args.in_dir).glob("*.json"))
            if not (out_dir / p.name).exists()]
    if args.limit:
        todo = todo[:args.limit]
    logging.info(f"{len(todo)} file(s) to grade with {MODEL}")

    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        sys.exit("No credentials: export ANTHROPIC_API_KEY=... and run again.")
    # read timeout: a stream that sends nothing for 5 min is dropped and retried
    client = anthropic.Anthropic(max_retries=5, timeout=anthropic.Timeout(900, read=300))
    tokens_in = tokens_out = 0
    failed = {}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(grade_file, client, p, out_dir): p for p in todo}
        for fut in as_completed(futures):
            path = futures[fut]
            try:
                usage = fut.result()
            except anthropic.AuthenticationError:
                logging.error("authentication failed: set ANTHROPIC_API_KEY")
                ex.shutdown(cancel_futures=True)
                sys.exit(1)
            except (anthropic.APIStatusError, anthropic.APIConnectionError,
                    RuntimeError, json.JSONDecodeError) as e:
                failed[path.name] = str(e)
                logging.warning(f"{path.name}: {e}")
                continue
            if usage:
                tokens_in += usage.input_tokens
                tokens_out += usage.output_tokens
            logging.info(f"graded {path.name}")

    # Sonnet 5: $2 / $10 per million input / output tokens
    cost = tokens_in * 2e-6 + tokens_out * 10e-6
    logging.info(f"done: {len(todo) - len(failed)} graded, {len(failed)} failed; "
                 f"{tokens_in:,} in / {tokens_out:,} out tokens ≈ ${cost:.2f}")
    if failed:
        (out_dir / "_failed.json").write_text(json.dumps(failed, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
