from pathlib import Path
from pathfinder.core.repo.MLRepo import MLRepo
from pathfinder.core.repo.repo_factory import get_degree_repo, get_ngd_repo

from src.pathfinder.core.repo.RetrieverRepo import RetrieverRepo

HERE = Path(__file__).parent


def test_MLRepo_using_retriever():
    ngd_path = HERE / "../../curie_ngd_v1.0_tier0-20260408.sqlite"
    kg2c_path = HERE / "../../tier0-info-for-overlay_v1.0_tier0-20260408.sqlite"
    ngd_path = f"sqlite:{ngd_path}"
    kg2c_path = f"sqlite:{kg2c_path}"
    degree_repo = get_degree_repo(kg2c_path)
    ngd_repo = get_ngd_repo(ngd_path)
    ml_repo = MLRepo(
        RetrieverRepo(5000, "https://retriever.ci.transltr.io/query", degree_repo),
        degree_repo,
        ngd_repo
    )

    edges, knowledge_graph = ml_repo.get_edges("CHEBI:45783")
    print("here")
