from pathfinder.PathRanker import PathRanker
from pathfinder.converter.ResultPerPathConverter import ResultPerPathConverter
from pathfinder.converter.EdgeExtractorFromTRAPIResponse import EdgeExtractorFromTRAPIResponse
from pathfinder.core.repo.GandalfRepo import GandalfRepo
from pathfinder.core.model.Node import Node
from pathfinder.core.model.Path import Path
from pathfinder.core.repo.repo_factory import get_repo, get_degree_repo


def get_paths(trapi_response, src_node_id, dst_node_id, src_pinned_node, dst_pinned_node):
    paths = set()
    for result in trapi_response["message"]["results"]:
        nodes = []
        node_bindings = result["node_bindings"]

        n1_id = node_bindings[src_pinned_node][0]['id']
        n1_info = trapi_response['message']['knowledge_graph']['nodes'][n1_id]
        nodes.append(Node(n1_id, weight=0.5, name=n1_info['name'], degree=10, category=n1_info['categories'][0]))

        inter0_id = node_bindings["intermediate_0"][0]['id']
        if inter0_id == dst_node_id or inter0_id == src_node_id:
            continue
        inter0_info = trapi_response['message']['knowledge_graph']['nodes'][inter0_id]
        nodes.append(
            Node(inter0_id, weight=0.5, name=inter0_info['name'], degree=10, category=inter0_info['categories'][0]))

        inter1_id = node_bindings["intermediate_1"][0]['id']
        if inter1_id == dst_node_id or inter1_id == src_node_id:
            continue
        inter1_info = trapi_response['message']['knowledge_graph']['nodes'][inter1_id]
        nodes.append(
            Node(inter1_id, weight=0.5, name=inter1_info['name'], degree=10, category=inter1_info['categories'][0]))

        n2_id = node_bindings[dst_pinned_node][0]['id']
        n2_info = trapi_response['message']['knowledge_graph']['nodes'][n2_id]
        nodes.append(Node(n2_id, weight=0.5, name=n2_info['name'], degree=10, category=n2_info['categories'][0]))

        paths.add(Path(0, nodes))

    return paths


class ThreeHopsPathfinder:

    def __init__(self, repository_name, repo_uri, ngd_url, degree_url, degree_threshold, limit, logger):
        self.repo_name = repository_name
        self.repo_uri = repo_uri
        self.ngd_url = ngd_url
        self.degree_url = degree_url
        self.degree_threshold = degree_threshold
        self.limit = limit
        self.logger = logger

    def find_three_hops_paths(self, node_id_1, node_id_2, src_pinned_node, dst_pinned_node, min_information_content):
        self.logger.info("Three hops pathfinder started.")
        if node_id_1 == node_id_2:
            self.logger.info("The two nodes are the same. Returning empty set.")
            return []


        pathfinder_request = {
            "message": {
                "auxiliary_graphs": {},
                "knowledge_graph": {
                    "edges": {},
                    "nodes": {}
                },
                "query_graph": {
                    "nodes": {
                        src_pinned_node: {
                            "ids": [
                                node_id_1
                            ]
                        },
                        dst_pinned_node: {
                            "ids": [
                                node_id_2
                            ]
                        }
                    },
                    "paths": {
                        "p0": {
                            "object": dst_pinned_node,
                            "subject": src_pinned_node
                        }
                    }
                },
                "results": []
            }
        }

        gandalf_repo = GandalfRepo(
            self.degree_threshold,
            gandalf_path=self.repo_uri.removeprefix("gandalf:"),
            degree_repo=get_degree_repo(self.degree_url)
        )

        trapi_response = gandalf_repo.get_3_hops_paths(node_id_1, node_id_2, src_pinned_node, dst_pinned_node, min_information_content)
        paths = get_paths(trapi_response, node_id_1, node_id_2, src_pinned_node, dst_pinned_node)

        edge_extractor = EdgeExtractorFromTRAPIResponse(trapi_response, self.logger)

        result, aux_graphs, knowledge_graph = ResultPerPathConverter(
            list(paths),
            node_id_1,
            node_id_2,
            src_pinned_node,
            dst_pinned_node,
            "aux",
            edge_extractor
        ).convert(self.logger)

        res = []
        if result is not None:
            res.append(
                {
                    "id": result["id"],
                    "analyses": result["analyses"],
                    "node_bindings": result["node_bindings"],
                    "essence": "result",
                }
            )
        if aux_graphs is None:
            aux_graphs = {}
        if knowledge_graph is None:
            knowledge_graph = {}
        pathfinder_request["message"]["knowledge_graph"] = knowledge_graph
        pathfinder_request["message"]["auxiliary_graphs"] = aux_graphs
        pathfinder_request["message"]["results"] = res

        path_ranker = PathRanker(
            "MLRepo",
            self.repo_uri,
            self.ngd_url,
            self.degree_url,
            self.limit
        )

        _, paths = path_ranker.rank_path(pathfinder_request)

        return paths
