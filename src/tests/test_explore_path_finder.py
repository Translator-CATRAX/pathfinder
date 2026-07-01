import json
import logging
import time
from pathlib import Path

import requests
from pathfinder.Pathfinder import Pathfinder

HERE = Path(__file__).parent

def download_file(url: str, out_path: Path, overwrite: bool = False) -> Path:
    out_path = Path(out_path)

    if out_path.exists() and not overwrite:
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)

    r = requests.get(url, timeout=60)
    r.raise_for_status()

    out_path.write_bytes(r.content)
    return out_path

def get_blocked_list():
    download_file("https://raw.githubusercontent.com/RTXteam/RTX/master/code/ARAX/KnowledgeSources/general_concepts.json", "general_concepts.json", False)

    with open("general_concepts.json", "r") as file:
        json_block_list = json.load(file)
    synonyms = set(s.lower() for s in json_block_list["synonyms"])
    return set(json_block_list["curies"]), synonyms

def test_pathfinder():
    blocked_curies, blocked_synonyms = get_blocked_list()
    src_node_id = "CHEBI:45783"
    dst_node_id = "MONDO:0004979"
    src_pinned_node = "n1"
    dst_pinned_node = "n2"
    pathfinder_request = {
        "message": {
            "auxiliary_graphs": {},
            "knowledge_graph": {
                "edges": {},
                "nodes": {}
            },
            "query_graph": {
                "nodes": {
                    src_pinned_node: {
                        "ids": [
                            src_node_id
                        ]
                    },
                    dst_pinned_node: {
                        "ids": [
                            dst_node_id
                        ]
                    }
                },
                "paths": {
                    "p0": {
                        "object": dst_pinned_node,
                        "subject": src_pinned_node
                    }
                }
            },
            "results": []
        }
    }

    HERE = Path(__file__).parent

    logger = logging.getLogger("tests.pathfinder")
    logger.setLevel(logging.INFO)

    ngd_path = HERE / "../../curie_ngd_v1.0_tier0-20260408.sqlite"
    kg2c_path = HERE / "../../tier0-info-for-overlay_v1.0_tier0-20260408.sqlite"
    pathfinder = Pathfinder(
        "MLRepo",
        f"gandalf:{HERE / '../../gandalf_mmap'}",
        f"sqlite:{ngd_path}",
        f"sqlite:{kg2c_path}",
        blocked_curies,
        blocked_synonyms,
        logger
    )
    start_time = time.perf_counter()
    result, aux_graphs, knowledge_graph = pathfinder.get_all_paths(
        src_node_id,
        dst_node_id,
        src_pinned_node,
        dst_pinned_node,
        4,
        4,
        500,
        75,
        30000,
        None
    )
    end_time = time.perf_counter()
    execution_time = end_time - start_time
    print(f"Executed in {execution_time:.6f} seconds")
    res = []
    if result is not None:
        res.append(
            {
                "id": result["id"],
                "analyses": result["analyses"],
                "node_bindings": result["node_bindings"],
                "essence": "result",
            }
        )
    if aux_graphs is None:
        aux_graphs = {}
    if knowledge_graph is None:
        knowledge_graph = {}
    pathfinder_request["message"]["knowledge_graph"] = knowledge_graph
    pathfinder_request["message"]["auxiliary_graphs"] = aux_graphs
    pathfinder_request["message"]["results"] = res
    json.dump(pathfinder_request, open(HERE / "path_response.json", "w"))
