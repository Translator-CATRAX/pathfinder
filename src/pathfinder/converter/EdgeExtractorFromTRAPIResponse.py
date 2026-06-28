class EdgeExtractorFromTRAPIResponse:

    def __init__(self, knowledge_graph, logger):
        self.logger = logger
        self.pairs_to_edge_ids = {}
        self.knowledge_graph = knowledge_graph
        for edge_id, info in knowledge_graph["edges"].items():
            edge_key_1 = f"{info["object"]}--{info["subject"]}"
            edge_key_2 = f"{info["subject"]}--{info["object"]}"
            if self.pairs_to_edge_ids.get(edge_key_1) is None and self.pairs_to_edge_ids.get(edge_key_2) is None:
                self.pairs_to_edge_ids[edge_key_1] = [edge_id]
            elif self.pairs_to_edge_ids.get(edge_key_1) is None:
                self.pairs_to_edge_ids[edge_key_2].append(edge_id)
            else:
                self.pairs_to_edge_ids[edge_key_1].append(edge_id)
        logger.info(f"Number of edges cached: {len(self.pairs_to_edge_ids)}")

    def get_edges(self, pairs, logger):
        cached_pairs = []
        i = 0
        while i < len(pairs):
            edge_key_1 = f"{pairs[i][0]}--{pairs[i][1]}"
            edge_key_2 = f"{pairs[i][1]}--{pairs[i][0]}"
            if edge_key_1 in self.pairs_to_edge_ids:
                cached_pairs.append(edge_key_1)
                del pairs[i]
            elif edge_key_2 in self.pairs_to_edge_ids:
                cached_pairs.append(edge_key_2)
                del pairs[i]
            else:
                i += 1
        if len(pairs) != 0:
            logger.error(f"Cannot retrieve {pairs} from trapi response.")
        knowledge_graph = {'edges': {}, 'nodes': {}}
        for cached_pair in cached_pairs:
            list_of_edges = self.pairs_to_edge_ids[cached_pair]
            cached_nodes = cached_pair.split("--")
            if cached_nodes[0] in self.knowledge_graph['nodes']:
                knowledge_graph['nodes'][cached_nodes[0]] = self.knowledge_graph['nodes'][cached_nodes[0]]
            if cached_nodes[1] in self.knowledge_graph['nodes']:
                knowledge_graph['nodes'][cached_nodes[1]] = self.knowledge_graph['nodes'][cached_nodes[1]]
            for edge in list_of_edges:
                if str(edge) in self.knowledge_graph['edges']:
                    knowledge_graph['edges'][str(edge)] = self.knowledge_graph['edges'][str(edge)]
        return knowledge_graph