import copy
import math
import queue
from concurrent.futures import ProcessPoolExecutor

from pathfinder.core.BreadthFirstSearch import traverse
from pathfinder.core.model.Node import Node
from pathfinder.core.model.Edge import Edge
from pathfinder.core.model.Path import Path
from pathfinder.core.model.PathContainer import PathContainer
from pathfinder.core.repo.repo_factory import get_repo


def run_bfs_process(hops_numbers, node_id, repo_args, prune_top_k, degree_threshold):
    repo = get_repo(*repo_args)

    path_container = PathContainer()
    path_queue = queue.Queue()

    new_path = Path.from_curie(hops_numbers, Node(curie=node_id))
    if hops_numbers != 0:
        path_queue.put(new_path)
    path_container.add_new_path(new_path)


    traverse(repo, path_queue, path_container, prune_top_k, degree_threshold)

    return path_container


class BidirectionalPathFinder:

    def __init__(self, repository_name, repo_uri, ngd_url, degree_url, prune_top_k, degree_threshold, logger):
        self.repo_name = repository_name
        self.repo_uri = repo_uri
        self.ngd_url = ngd_url
        self.degree_url = degree_url
        self.prune_top_k = prune_top_k
        self.degree_threshold = degree_threshold
        self.logger = logger


    def find_all_paths(self, node_id_1, node_id_2, hops_numbers=1):
        self.logger.info("Finding paths process has started")
        result = set()
        if hops_numbers == 0:
            return result
        if node_id_1 == node_id_2:
            return result

        hops_numbers_1 = math.floor((hops_numbers + 1) / 2)
        hops_numbers_2 = math.floor(hops_numbers / 2)

        repo_args = (self.repo_name, self.repo_uri, self.ngd_url, self.degree_url, self.degree_threshold)

        with ProcessPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(run_bfs_process, hops_numbers_1, node_id_1, repo_args, self.prune_top_k, self.degree_threshold)
            f2 = ex.submit(run_bfs_process, hops_numbers_2, node_id_2, repo_args, self.prune_top_k, self.degree_threshold)

            try:
                path_container_1 = f1.result()
            except Exception as e:
                self.logger.error(f"Process 1 with curie id: {node_id_1} failed with exception: {e}")
                path_container_1 = None

            try:
                path_container_2 = f2.result()
            except Exception as e:
                self.logger.error(f"Process 2 with curie id: {node_id_2} failed with exception: {e}")
                path_container_2 = None

        intersection_list = path_container_1.path_dict.keys() & path_container_2.path_dict.keys()

        for node in intersection_list:
            for path_1 in path_container_1.path_dict[node]:
                for path_2 in path_container_2.path_dict[node]:
                    temp_path_1 = copy.deepcopy(path_1)
                    for i in range(len(path_2.edges) - 1, -1, -1):
                        new_edge = Edge(path_2.edges[i].target, path_2.edges[i].source, path_2.edges[i].weight_bar, path_2.edges[i].weight)
                        temp_path_1.edges.append(new_edge)

                    if len(temp_path_1.node_list()) == len(temp_path_1.node_set()):
                        result.add(Path(0, temp_path_1.edges))

        result = sorted(list(result), key=lambda path: path.compute_weight(), reverse=True)

        return result
