import logging
import time
from pathlib import Path

from pathfinder.Pathfinder import Pathfinder

HERE = Path(__file__).parent
def test_pathfinder():
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
        {},
        {},
        logger
    )
    start_time = time.perf_counter()
    response = pathfinder.get_paths(
        "CHEBI:45783",
        "MONDO:0004979",
        "n1",
        "n2",
        4,
        4,
        100,
        100,
        20000,
        None
    )
    end_time = time.perf_counter()
    execution_time = end_time - start_time
    print(f"Executed in {execution_time:.6f} seconds")
    assert response[0]["analyses"][0]["score"] > 0
