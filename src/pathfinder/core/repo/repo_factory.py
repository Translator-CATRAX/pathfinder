from pathfinder.core.repo.MLRepo import MLRepo
from pathfinder.core.repo.NGDRepository import NGDRepository
from pathfinder.core.repo.NGDSortedNeighborsRepo import NGDSortedNeighborsRepo
from pathfinder.core.repo.NodeDegreeRepo import NodeDegreeRepo
from pathfinder.core.repo.PloverDBRepo import PloverDBRepo


def get_repo(repo_name, plover_url, ngd_url, degree_url):
    if repo_name == "NGDSortedNeighborsRepo":
        return NGDSortedNeighborsRepo(
            PloverDBRepo(plover_url=plover_url, degree_repo=NodeDegreeRepo(degree_url)),
            NodeDegreeRepo(degree_url),
            NGDRepository(ngd_url)
        )
    elif repo_name == "MLRepo":
        return MLRepo(
            PloverDBRepo(plover_url=plover_url, degree_repo=NodeDegreeRepo(degree_url)),
            NodeDegreeRepo(degree_url),
            NGDRepository(ngd_url)
        )
    else:
        raise ValueError(f"Unknown animal_type '{repo_name}'.")
