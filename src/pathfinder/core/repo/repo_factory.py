from pathfinder.core.repo.MLRepo import MLRepo
from pathfinder.core.repo.NGDRepository import NGDRepository
from pathfinder.core.repo.NGDSortedNeighborsRepo import NGDSortedNeighborsRepo
from pathfinder.core.repo.NodeDegreeRepo import NodeDegreeRepo
from pathfinder.core.repo.PloverDBRepo import PloverDBRepo
from pathfinder.core.repo.MysqlNGDRepository import MysqlNGDRepository
from pathfinder.core.repo.MysqlNodeDegreeRepo import MysqlNodeDegreeRepo


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


def get_repo(repo_name, plover_url, ngd_url, degree_url):
    if repo_name == "NGDSortedNeighborsRepo":
        return NGDSortedNeighborsRepo(
            PloverDBRepo(plover_url=plover_url, degree_repo=NodeDegreeRepo(degree_url)),
            get_degree_repo(degree_url),
            get_ngd_repo(ngd_url)
        )
    elif repo_name == "MLRepo":
        return MLRepo(
            PloverDBRepo(plover_url=plover_url, degree_repo=NodeDegreeRepo(degree_url)),
            get_degree_repo(degree_url),
            get_ngd_repo(ngd_url)
        )
    else:
        raise ValueError(f"Unknown animal_type '{repo_name}'.")
