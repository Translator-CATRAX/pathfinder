import copy


class LocalRepo:

    def __init__(self, pathfinder_response):

        self.kg = copy.deepcopy(pathfinder_response["message"]["knowledge_graph"])
        self.nodes = copy.deepcopy(pathfinder_response["message"]["knowledge_graph"]["nodes"])

        for edge_id, edge_info in pathfinder_response["message"]["knowledge_graph"]["edges"].items():
            sub = edge_info["subject"]
            obj = edge_info["object"]
            predicate = edge_info["predicate"]
            if sub in self.nodes:
                if "neighbors" not in self.nodes[sub]:
                    self.nodes[sub]["neighbors"] = {}
                if obj not in self.nodes[sub]["neighbors"]:
                    self.nodes[sub]["neighbors"][obj] = {
                        "name": pathfinder_response["message"]["knowledge_graph"]["nodes"][obj]["name"],
                        "category": pathfinder_response["message"]["knowledge_graph"]["nodes"][obj]["categories"][0],
                        "predicates": [predicate]
                    }
                else:
                    self.nodes[sub]["neighbors"][obj]["predicates"].append(predicate)
            if obj in self.nodes:
                if "neighbors" not in self.nodes[obj]:
                    self.nodes[obj]["neighbors"] = {}
                if sub not in self.nodes[obj]["neighbors"]:
                    self.nodes[obj]["neighbors"][sub] = {
                        "name": pathfinder_response["message"]["knowledge_graph"]["nodes"][sub]["name"],
                        "category": pathfinder_response["message"]["knowledge_graph"]["nodes"][sub]["categories"][0],
                        "predicates": [predicate]
                    }
                else:
                    self.nodes[obj]["neighbors"][sub]["predicates"].append(predicate)

    def get_neighbors_with_edges(self, curie):
        edges = {}
        for neighbor, info in self.nodes[curie]["neighbors"].items():
            if neighbor not in edges:
                edges[neighbor] = []
            edges[neighbor].extend(info["predicates"])
        return self.nodes[curie]["name"], self.nodes[curie]["categories"][0], self.nodes[curie]["neighbors"], edges, self.kg
