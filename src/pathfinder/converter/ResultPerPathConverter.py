from pathfinder.converter.PathConverter import PathConverter


class ResultPerPathConverter:

    def __init__(
            self,
            paths,
            node_1_id,
            node_2_id,
            qnode_1_id,
            qnode_2_id,
            aux_name,
            edge_extractor,
    ):
        self.paths = paths
        self.node_1_id = node_1_id
        self.node_2_id = node_2_id
        self.qnode_1_id = qnode_1_id
        self.qnode_2_id = qnode_2_id
        self.aux_name = aux_name
        self.edge_extractor = edge_extractor

    def convert(self, logger):
        self.extract_edges(logger)

        aux_graphs = {}
        analyses = []
        knowledge_graph = {'edges': {}, 'nodes': {}}

        i = 0
        for path in self.paths:
            i = i + 1
            analysis, aux_graph, kg = PathConverter(
                path,
                self.qnode_1_id,
                self.qnode_2_id,
                f"{self.aux_name}_{i}",
                self.edge_extractor,
                path.compute_weight(),
            ).convert(logger)
            aux_graphs[f"{self.aux_name}_{i}"] = aux_graph
            analyses.append(analysis)
            knowledge_graph['edges'].update(kg['edges'])
            knowledge_graph['nodes'].update(kg['nodes'])

        result = {
            "id": "result",
            "analyses": analyses,
            "node_bindings": {
                self.qnode_1_id: [
                    {
                        "id": self.node_1_id,
                        "attributes": []
                    }
                ],
                self.qnode_2_id: [
                    {
                        "id": self.node_2_id,
                        "attributes": []
                    }
                ]
            },
            "essence": "result",
            "resource_id": "infores:arax",
        }

        return result, aux_graphs, knowledge_graph

    def extract_edges(self, logger):
        edges = set()
        for path in self.paths:
            edges.update(path.edges)
            if len(edges) > 200:
                pair_list = []
                for edge in edges:
                    pair_list.append([edge.source.id, edge.target.id])
                self.edge_extractor.get_edges(pair_list, logger)
                edges = set()
        if len(edges) > 0:
            pair_list = []
            for edge in edges:
                pair_list.append([edge.source.id, edge.target.id])
            self.edge_extractor.get_edges(pair_list, logger)
