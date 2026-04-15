import gc

from pathfinder.core.repo.Repository import Repository
from gandalf import CSRGraph, lookup
from bmt import Toolkit

class GandalfRepo:

    def __init__(self, gandalf_path, degree_repo):
        self.graph = CSRGraph.load_mmap(gandalf_path)
        self.bmt = Toolkit()
        # Freeze all objects allocated so far (graph + BMT) into a permanent
        # generation that the cyclic GC will never scan.  This makes Gen 2
        # collections cheap because they skip the large CSR arrays.
        gc.collect()
        gc.freeze()
        # Raise thresholds so Gen 2 collections are less frequent even for
        # the (now-small) unfrozen query-time object set.
        gc.set_threshold(50_000, 50, 50)
        self.degree_repo = degree_repo

    def get_neighbors_with_edges(self, curie):
        response = lookup(
            self.graph,
            {
                "message": {
                    "query_graph": {
                        "nodes": {
                            "n1": {"ids": [curie]},
                            "n2": {"categories": ["biolink:NamedThing"]}
                        },
                        "edges": {
                            "e1": {"subject": "n1", "object": "n2"}
                        }
                    }
                }
            },
            self.bmt,
            dehydrated=True
        )
        nodes = {}
        edges = {}
        for _, info in response['message']['knowledge_graph']['edges'].items():
            if info['object'] == curie:
                neighbor_id = info['subject']
            elif info['subject'] == curie:
                neighbor_id = info['object']
            else:
                continue
            nodes[neighbor_id] = {}
            nodes[neighbor_id]['name'] = response['message']['knowledge_graph']['nodes'][neighbor_id]['name']
            nodes[neighbor_id]['category'] = response['message']['knowledge_graph']['nodes'][neighbor_id]['categories'][0]
            if neighbor_id not in edges:
                edges[neighbor_id] = [info['predicate']]
            else:
                edges[neighbor_id].append(info['predicate'])
        if curie in response['message']['knowledge_graph']['nodes']:
            return response['message']['knowledge_graph']['nodes'][curie]['categories'][0], nodes, edges
        return None, None, None



    def get_node_degree(self, node_id):
        return self.degree_repo.get_node_degree(node_id)

