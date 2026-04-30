from gandalf import CSRGraph, lookup
from bmt import Toolkit


class EdgeExtractorFromGandalf:

    def __init__(self, gandalf_path):
        self.graph = CSRGraph.load_mmap(gandalf_path)
        self.bmt = Toolkit()
        self.pairs_to_edge_ids = {}
        self.knowledge_graph = {'edges': {}, 'nodes': {}}

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
        knowledge_graph = {'edges': {}, 'nodes': {}}
        for pair in pairs:
            response = lookup(
                self.graph,
                {
                    "message": {
                        "query_graph": {
                            "nodes": {
                                "n1": {"ids": [pair[0]]},
                                "n2": {"ids": [pair[1]]}
                            },
                            "edges": {
                                "e1": {"subject": "n1", "object": "n2"},
                                "e2": {"subject": "n2", "object": "n1"},
                            }
                        }
                    }
                },
                self.bmt,
                dehydrated=False,
                subclass=False
            )
            pair_key = f"{pair[0]}--{pair[1]}"
            if pair_key not in self.pairs_to_edge_ids:
                self.pairs_to_edge_ids[pair_key] = list(response['message']['knowledge_graph']['edges'].keys())
            else:
                self.pairs_to_edge_ids[pair_key].extend(response['message']['knowledge_graph']['edges'].keys())
            knowledge_graph['edges'].update(response['message']['knowledge_graph']['edges'])
            knowledge_graph['nodes'].update(response['message']['knowledge_graph']['nodes'])
            self.knowledge_graph['edges'].update(response['message']['knowledge_graph']['edges'])
            self.knowledge_graph['nodes'].update(response['message']['knowledge_graph']['nodes'])
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
