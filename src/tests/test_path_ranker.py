import json
from pathlib import Path
from pathfinder.PathRanker import PathRanker

HERE = Path(__file__).parent


def test_rank_path():
    one_hop_query = json.loads((HERE / "pathfinder-one-hop-response.json").read_text())

    ngd_path = HERE / "../../curie_ngd_v1.0_tier0-20260408.sqlite"
    kg2c_path = HERE / "../../tier0-info-for-overlay_v1.0_tier0-20260408.sqlite"
    path_ranker = PathRanker(
        f"gandalf:{HERE / '../../gandalf_mmap'}",
        f"sqlite:{ngd_path}",
        f"sqlite:{kg2c_path}"
    )
    assert one_hop_query["message"]["results"][0]["analyses"][0]['score'] == 0.031344910561234354
    pathfinder_response, _ = path_ranker.rank_path(one_hop_query)
    assert pathfinder_response["message"]["results"][0]["analyses"][0]['score'] != 0.031344910561234354
    assert pathfinder_response["message"]["results"][0]["analyses"][0]['score'] > 0

    json.dump(pathfinder_response, open(HERE / "new_scores.json", "w"))
