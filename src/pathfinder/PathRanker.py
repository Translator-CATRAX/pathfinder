import heapq
import itertools

from pathfinder.core.repo.LocalRepo import LocalRepo
from pathfinder.core.repo.MLRepo import MLRepo
from pathfinder.core.repo.repo_factory import get_repo
from pathfinder.core.model.Node import Node
from pathfinder.core.model.Path import Path
from pathfinder.core.repo.repo_factory import get_degree_repo, get_ngd_repo


class PathRanker:

    def __init__(self, repo_name, repo_uri, ngd_url, degree_url, max_size=0):
        self.repo_name = repo_name
        self.repo_uri = repo_uri
        self.ngd_url = ngd_url
        self.degree_url = degree_url
        self.max_size = max_size

    def rank_path(self, pathfinder_response):
        local_repo = LocalRepo(pathfinder_response)

        nodes = {}
        ml_repo = MLRepo(local_repo, get_degree_repo(self.degree_url), get_ngd_repo(self.ngd_url))
        for node in pathfinder_response["message"]["knowledge_graph"]["nodes"].keys():
            node_neighbors = ml_repo.get_neighbors(Node(id=node), 10_000_000)
            for neighbor in node_neighbors:
                if node not in nodes:
                    nodes[node] = {}
                nodes[node][neighbor.id] = neighbor

        queried_path = next(iter(pathfinder_response["message"]["query_graph"]["paths"].values()))
        src_pinned_node = queried_path["subject"]
        dst_pinned_node = queried_path["object"]
        src_node_id = pathfinder_response["message"]["query_graph"]["nodes"][src_pinned_node]["ids"][0]
        dst_node_id = pathfinder_response["message"]["query_graph"]["nodes"][dst_pinned_node]["ids"][0]

        paths = []
        tiebreaker = itertools.count()

        for analyses in pathfinder_response["message"]["results"][0]["analyses"]:
            current_node = src_node_id
            aux_id = next(iter(analyses["path_bindings"].values()))[0]['id']
            links = []
            links_set = set()
            prev_weight = None
            while current_node != dst_node_id:
                for edge in pathfinder_response["message"]["auxiliary_graphs"][aux_id]["edges"]:
                    if pathfinder_response["message"]["knowledge_graph"]["edges"][edge]['subject'] == current_node:
                        connected_node = pathfinder_response["message"]["knowledge_graph"]["edges"][edge]['object']
                    elif pathfinder_response["message"]["knowledge_graph"]["edges"][edge]['object'] == current_node:
                        connected_node = pathfinder_response["message"]["knowledge_graph"]["edges"][edge]['subject']
                    else:
                        continue
                    if connected_node in links_set:
                        continue
                    links_set.add(current_node)
                    weight = nodes[connected_node][current_node].weight
                    if prev_weight is not None:
                        weight = (weight + prev_weight) / 2
                    links.append(
                        Node(
                            id=current_node,
                            weight=weight,
                            name=nodes[connected_node][current_node].name,
                            degree=nodes[connected_node][current_node].degree,
                            category=nodes[connected_node][current_node].category
                        )
                    )
                    prev_weight = nodes[current_node][connected_node].weight
                    if connected_node == dst_node_id:
                        links.append(
                            Node(
                                id=connected_node,
                                weight=nodes[current_node][connected_node].weight,
                                name=nodes[current_node][connected_node].name,
                                degree=nodes[current_node][connected_node].degree,
                                category=nodes[current_node][connected_node].category
                            )
                        )
                    current_node = connected_node
                    break

            path = Path(0, links)
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
