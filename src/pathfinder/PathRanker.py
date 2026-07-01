import heapq
import itertools

from pathfinder.core.repo.LocalRepo import LocalRepo
from pathfinder.core.repo.MLRepo import MLRepo
from pathfinder.core.repo.repo_factory import get_repo
from pathfinder.core.model.Node import Node
from pathfinder.core.model.Edge import Edge
from pathfinder.core.model.Path import Path
from pathfinder.core.repo.repo_factory import get_degree_repo, get_ngd_repo


class PathRanker:

    def __init__(self, repo_name: str, repo_uri: str, ngd_url: str, degree_url: str, max_size: int = 0):
        self.repo_name = repo_name
        self.repo_uri = repo_uri
        self.ngd_url = ngd_url
        self.degree_url = degree_url
        self.max_size = max_size

    def rank_path(self, pathfinder_response: dict) -> tuple[dict, list[Path]]:
        local_repo = LocalRepo(pathfinder_response)

        nodes = {}
        ml_repo = MLRepo(local_repo, get_degree_repo(self.degree_url), get_ngd_repo(self.ngd_url))
        for curie in pathfinder_response["message"]["knowledge_graph"]["nodes"].keys():
            edges = ml_repo.get_edges(curie)
            for edge in edges:
                if edge.source.id not in nodes:
                    nodes[edge.source.id] = {}
                nodes[edge.source.id][edge.target.id] = edge

        queried_path = next(iter(pathfinder_response["message"]["query_graph"]["paths"].values()))
        src_pinned_node = queried_path["subject"]
        dst_pinned_node = queried_path["object"]
        src_node_id = pathfinder_response["message"]["query_graph"]["nodes"][src_pinned_node]["ids"][0]
        dst_node_id = pathfinder_response["message"]["query_graph"]["nodes"][dst_pinned_node]["ids"][0]

        paths = []
        tiebreaker = itertools.count()

        for analyses in pathfinder_response["message"]["results"][0]["analyses"]:
            current_id = src_node_id
            aux_id = next(iter(analyses["path_bindings"].values()))[0]['id']
            edges = []
            nodes_set = set()
            while current_id != dst_node_id:
                for edge in pathfinder_response["message"]["auxiliary_graphs"][aux_id]["edges"]:
                    if pathfinder_response["message"]["knowledge_graph"]["edges"][edge]['subject'] == current_id:
                        connected_id = pathfinder_response["message"]["knowledge_graph"]["edges"][edge]['object']
                    elif pathfinder_response["message"]["knowledge_graph"]["edges"][edge]['object'] == current_id:
                        connected_id = pathfinder_response["message"]["knowledge_graph"]["edges"][edge]['subject']
                    else:
                        continue
                    if connected_id in nodes_set:
                        continue
                    nodes_set.add(current_id)
                    weight = nodes[current_id][connected_id].weight
                    weight_bar = nodes[connected_id][current_id].weight

                    src_node = Node(
                        curie=current_id,
                        name=nodes[connected_id][current_id].target.name,
                        degree=nodes[connected_id][current_id].target.degree,
                        category=nodes[connected_id][current_id].target.category
                    )
                    dst_node = Node(
                        curie=connected_id,
                        name=nodes[current_id][connected_id].target.name,
                        degree=nodes[current_id][connected_id].target.degree,
                        category=nodes[current_id][connected_id].target.category
                    )
                    edges.append(
                        Edge(src_node, dst_node, weight, weight_bar)
                    )
                    current_id = connected_id
                    break

            path = Path(0, edges)
            weight = path.compute_weight()
            count = next(tiebreaker)
            if self.max_size != 0:
                if len(paths) < self.max_size:
                    heapq.heappush(paths, (weight, count, path))
                else:
                    if weight > paths[0][0]:
                        heapq.heappushpop(paths, (weight, count, path))
            analyses["score"] = weight

        paths = sorted(paths, key=lambda x: x[0], reverse=True)

        return pathfinder_response, [path for _, _, path in paths]
