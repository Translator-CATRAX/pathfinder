import queue

from pathfinder.core.BreadthFirstSearch import traverse
from pathfinder.core.model.Node import Node
from pathfinder.core.model.Path import Path
from pathfinder.core.model.PathContainer import PathContainer
from pathfinder.core.repo.repo_factory import get_repo

class PathRanker:
    def __init__(self, repo_name, plover_url, ngd_url, degree_url):
        self.repo_name = repo_name
        self.plover_url = plover_url
        self.ngd_url = ngd_url
        self.degree_url = degree_url
        self.degree_threshold = 40000
        self.prune_top_k = 10000000

    def rank_path(self, trapi_structure):
        edges = trapi_structure["message"]["knowledge_graph"]["edges"]
        neighbors_by_node = {}
        for _, value in edges.items():
            n1 = Node(value["object"])
            n2 = Node(value["subject"])
            if n1 not in neighbors_by_node:
                neighbors_by_node[n1] = {}
            neighbors_by_node[n1][n2.id] = n2
            if n2 not in neighbors_by_node:
                neighbors_by_node[n2] = {}
            neighbors_by_node[n2][n1.id] = n1
        sorted_nodes = sorted(neighbors_by_node.items(), key=lambda kv: len(kv[1]), reverse=True)

        path_container = PathContainer()
        path_queue = queue.Queue()
        for node, _ in sorted_nodes:
            new_path = Path(1, [node])
            path_queue.put(new_path)
            path_container.add_new_path(new_path)

        repo = get_repo(self.repo_name, self.plover_url, self.ngd_url, self.degree_url, self.degree_threshold)

        traverse(repo, path_queue, path_container, self.prune_top_k, self.degree_threshold)

        for _, paths in path_container.path_dict.items():
            for path in paths:
                if len(path.links) != 2:
                    continue
                if path.links[0] in neighbors_by_node:
                    if path.links[1].id in neighbors_by_node[path.links[0]]:
                        neighbors_by_node[path.links[0]][path.links[1].id].weight = path.links[1].weight
                        neighbors_by_node[path.links[0]][path.links[1].id].name = path.links[1].name
                        neighbors_by_node[path.links[0]][path.links[1].id].degree = path.links[1].degree
                        neighbors_by_node[path.links[0]][path.links[1].id].category = path.links[1].category

        path = next(iter(trapi_structure["message"]["query_graph"]["paths"].values()))
        subject_node = path["subject"]
        object_node = path["object"]
        sub_id = trapi_structure["message"]["query_graph"]["nodes"][subject_node]["ids"][0]
        obj_id = trapi_structure["message"]["query_graph"]["nodes"][object_node]["ids"][0]

        for analyses in trapi_structure["message"]["results"][0]["analyses"]:
            nodes = {}
            aux_id = next(iter(analyses["path_bindings"].values()))[0]["id"]
            edges = trapi_structure["message"]["auxiliary_graphs"][aux_id]["edges"]
            for edge_id in edges:
                edge = trapi_structure["message"]["knowledge_graph"]["edges"][edge_id]
                obj = edge["object"]
                sub = edge["subject"]
                if sub in nodes:
                    nodes[sub].append(obj)
                else:
                    nodes[sub] = [obj]
                if obj in nodes:
                    nodes[obj].append(sub)
                else:
                    nodes[obj] = [sub]

            node_list = []
            next_item = sub_id
            prev = None
            while next_item != None:
                current = next_item
                node_list.append(current)
                next_item = None
                for neighbor in nodes[current]:
                    if neighbor != prev:
                        next_item = neighbor
                        break
                prev = current

            path = Path(0, None)
            for i in range(len(node_list)):
                if i == len(node_list) - 1:
                    next_node = neighbors_by_node[Node(node_list[i])][node_list[i - 1]]
                    current = neighbors_by_node[Node(node_list[i - 1])][node_list[i]]
                else:
                    next_node = neighbors_by_node[Node(node_list[i])][node_list[i + 1]]
                    current = neighbors_by_node[Node(node_list[i + 1])][node_list[i]]
                current.weight = (current.weight + next_node.weight) / 2
                path = path.make_new_path(current, None)

            analyses["score"] = path.compute_weight()