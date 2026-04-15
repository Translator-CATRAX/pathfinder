import logging
import time
from pathlib import Path

from pathfinder.core.BidirectionalPathFinder import BidirectionalPathFinder

HERE = Path(__file__).parent
def test_bidirectional_pathfinder_with_gandalf():
    HERE = Path(__file__).parent

    logger = logging.getLogger("tests.pathfinder")
    logger.setLevel(logging.INFO)

    ngd_path = HERE / "../../curie_ngd_v1.0_KG2.10.2.sqlite"
    kg2c_path = HERE / "../../kg2c_v1.0_KG2.10.2.sqlite"
    pathfinder = BidirectionalPathFinder(
        "MLRepo",
        f"gandalf:{HERE / '../../data/processed/gandalf_mmap'}",
        f"sqlite:{ngd_path}",
        f"sqlite:{kg2c_path}",
        100,
        100000000,
        logger
    )
    start_time = time.perf_counter()
    response = pathfinder.find_all_paths(
        "CHEBI:45783",
        "MONDO:0004979",
        4
    )
    end_time = time.perf_counter()
    execution_time = end_time - start_time
    print(f"Executed in {execution_time:.6f} seconds")
    print(len(response))
    assert len(response) > 0
