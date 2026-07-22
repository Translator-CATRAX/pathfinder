import logging
import time
from pathlib import Path

from pathfinder.Pathfinder import Pathfinder
from tests.test_utility import get_blocked_list, save_trapi_response

HERE = Path(__file__).parent

def test_pathfinder():
    blocked_curies, blocked_synonyms = get_blocked_list()
    src_node_id = "CHEBI:45783"
    dst_node_id = "MONDO:0004979"
    src_pinned_node = "n1"
    dst_pinned_node = "n2"
    HERE = Path(__file__).parent

    logger = logging.getLogger("tests.pathfinder")
    logger.setLevel(logging.INFO)

    ngd_path = HERE / "../../curie_ngd_v1.0_tier0-20260621.sqlite"
    kg2c_path = HERE / "../../tier0-info-for-overlay_v1.0_tier0-20260621.sqlite"
    pathfinder = Pathfinder(
        f"retriever:https://retriever.ci.transltr.io/query",
        f"sqlite:{ngd_path}",
        f"sqlite:{kg2c_path}",
        blocked_curies,
        blocked_synonyms,
        logger
    )
    start_time = time.perf_counter()
    result, aux_graphs, knowledge_graph = pathfinder.get_three_hops_paths(
        src_node_id,
        dst_node_id,
        src_pinned_node,
        dst_pinned_node,
        500,
        5000,
        None,
        69
    )
    end_time = time.perf_counter()
    execution_time = end_time - start_time
    print(f"Executed in {execution_time:.6f} seconds")
    save_trapi_response(
        HERE / "3_hops_using_retriever.json",
        result,
        aux_graphs,
        knowledge_graph,
        src_node_id,
        dst_node_id,
        src_pinned_node,
        dst_pinned_node,
    )
