import logging
import json
from pathlib import Path
from pathfinder.PathRanker import PathRanker


HERE = Path(__file__).parent
def test_rank_path():
    HERE = Path(__file__).parent
    one_hop_query = json.loads((HERE / "pathfinder-one-hop-response.json").read_text())

    logger = logging.getLogger("tests.pathfinder")
    logger.setLevel(logging.INFO)

    ngd_path = HERE / "../../curie_ngd_v1.0_KG2.10.2.sqlite"
    kg2c_path = HERE / "../../kg2c_v1.0_KG2.10.2.sqlite"
    path_ranker = PathRanker(
        "MLRepo",
        "https://kg2cploverdb.ci.transltr.io",
        f"sqlite:{ngd_path}",
        f"sqlite:{kg2c_path}",
        logger
    )
    ranked_response = path_ranker.rank_path(one_hop_query)
    assert ranked_response["message"]["results"]["analyses"][0]["score"] != 0.99
