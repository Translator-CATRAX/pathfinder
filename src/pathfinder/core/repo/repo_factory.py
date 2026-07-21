from pathfinder.core.repo.MLRepo import MLRepo
from pathfinder.core.repo.NGDRepository import NGDRepository
from pathfinder.core.repo.NGDSortedNeighborsRepo import NGDSortedNeighborsRepo
from pathfinder.core.repo.NodeDegreeRepo import NodeDegreeRepo
from pathfinder.core.repo.MysqlNGDRepository import MysqlNGDRepository
from pathfinder.core.repo.MysqlNodeDegreeRepo import MysqlNodeDegreeRepo
from pathfinder.core.repo.GandalfRepo import GandalfRepo
from pathfinder.core.repo.RetrieverRepo import RetrieverRepo


def get_ngd_repo(ngd_url):
    if ngd_url.startswith("sqlite:"):
        return NGDRepository(ngd_url.removeprefix("sqlite:"))
    elif ngd_url.startswith("mysql:"):
        return MysqlNGDRepository.from_config_string(ngd_url)
    else:
        raise ValueError(f"Unknown ngd_url '{ngd_url}'.")

def get_degree_repo(degree_url):
    if degree_url.startswith("sqlite:"):
        return NodeDegreeRepo(degree_url.removeprefix("sqlite:"))
    elif degree_url.startswith("mysql:"):
        return MysqlNodeDegreeRepo.from_config_string(degree_url)
    else:
        raise ValueError(f"Unknown ngd_url '{degree_url}'.")

def get_kg_repo(repo_uri, degree_repo, node_degree_threshold):
    if repo_uri.startswith("gandalf:"):
        return GandalfRepo(node_degree_threshold, gandalf_path=repo_uri.removeprefix("gandalf:"), degree_repo=degree_repo)
    elif repo_uri.startswith("retriever:"):
        return RetrieverRepo(node_degree_threshold, retriever_path=repo_uri.removeprefix("retriever:"), degree_repo=degree_repo)
    else:
        raise ValueError(f"Unknown repo uri Starting with: '{repo_uri}'.")


def get_repo(repo_uri, ngd_url, degree_url, node_degree_threshold):
    degree_repo = get_degree_repo(degree_url)
    ngd_repo = get_ngd_repo(ngd_url)
    return MLRepo(
            get_kg_repo(repo_uri, degree_repo, node_degree_threshold),
            degree_repo,
            ngd_repo
        )