import gc

from pathfinder.core.repo.Repository import Repository
from gandalf import CSRGraph, lookup
from bmt import Toolkit

class GandalfRepo:

    def __init__(self, node_degree_threshold, gandalf_path, degree_repo):
        self.node_degree_threshold = node_degree_threshold
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
            subclass=False,
            filter_config={"max_node_degree": self.node_degree_threshold},
            dehydrated=True,
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

    def get_3_hops_paths(self, src, dst, src_pinned_node, dst_pinned_node, min_information_content):
        response = lookup(
            self.graph,
            {
                "message": {
                    "query_graph": {
                        "nodes": {
                            src_pinned_node: {"ids": [src]},
                            "intermediate_0": {
                                "categories": ["biolink:NamedThing"],
                            },
                            "intermediate_1": {
                                "categories": ["biolink:NamedThing"],
                            },
                            dst_pinned_node: {"ids": [dst]},
                        },
                        "edges": {
                            "e0": {
                                "subject": src_pinned_node,
                                "object": "intermediate_0",
                                "predicates": [
                                    "biolink:physically_interacts_with",
                                    "biolink:genetically_interacts_with",
                                    "biolink:contributes_to",
                                    "biolink:contribution_from",
                                    "biolink:affects",
                                    "biolink:affected_by",
                                    "biolink:acts_upstream_of",
                                    "biolink:has_upstream_actor",
                                    "biolink:enables",
                                    "biolink:enabled_by",
                                    "biolink:produces",
                                    "biolink:produced_by",
                                    "biolink:has_participant",
                                    "biolink:participates_in",
                                    "biolink:derives_from",
                                    "biolink:derives_into",
                                    "biolink:transcribed_to",
                                    "biolink:transcribed_from",
                                    "biolink:translates_to",
                                    "biolink:translation_of",
                                    "biolink:has_gene_product",
                                    "biolink:gene_product_of",
                                    "biolink:genetically_associated_with",
                                ],
                            },
                            "e1": {
                                "subject": "intermediate_0",
                                "object": "intermediate_1",
                                "predicates": [
                                    "biolink:physically_interacts_with",
                                    "biolink:genetically_interacts_with",
                                    "biolink:contributes_to",
                                    "biolink:contribution_from",
                                    "biolink:affects",
                                    "biolink:affected_by",
                                    "biolink:acts_upstream_of",
                                    "biolink:has_upstream_actor",
                                    "biolink:enables",
                                    "biolink:enabled_by",
                                    "biolink:produces",
                                    "biolink:produced_by",
                                    "biolink:has_participant",
                                    "biolink:participates_in",
                                    "biolink:derives_from",
                                    "biolink:derives_into",
                                    "biolink:transcribed_to",
                                    "biolink:transcribed_from",
                                    "biolink:translates_to",
                                    "biolink:translation_of",
                                    "biolink:has_gene_product",
                                    "biolink:gene_product_of",
                                    "biolink:genetically_associated_with",
                                ],
                            },
                            "e2": {
                                "subject": "intermediate_1",
                                "object": dst_pinned_node,
                                "predicates": [
                                    "biolink:physically_interacts_with",
                                    "biolink:genetically_interacts_with",
                                    "biolink:contributes_to",
                                    "biolink:contribution_from",
                                    "biolink:affects",
                                    "biolink:affected_by",
                                    "biolink:acts_upstream_of",
                                    "biolink:has_upstream_actor",
                                    "biolink:enables",
                                    "biolink:enabled_by",
                                    "biolink:produces",
                                    "biolink:produced_by",
                                    "biolink:has_participant",
                                    "biolink:participates_in",
                                    "biolink:derives_from",
                                    "biolink:derives_into",
                                    "biolink:transcribed_to",
                                    "biolink:transcribed_from",
                                    "biolink:translates_to",
                                    "biolink:translation_of",
                                    "biolink:has_gene_product",
                                    "biolink:gene_product_of",
                                    "biolink:genetically_associated_with",
                                ],
                            },
                        },
                    }
                }
            },
            self.bmt,
            subclass=False,
            filter_config={"max_node_degree": self.node_degree_threshold, "min_information_content": min_information_content},
            dehydrated=True,
        )
        return response

    def get_2_hops_paths(self, src, dst, src_pinned_node, dst_pinned_node, min_information_content):
        response = lookup(
            self.graph,
            {
                "message": {
                    "query_graph": {
                        "nodes": {
                            src_pinned_node: {"ids": [src]},
                            "intermediate_0": {
                                "categories": ["biolink:NamedThing"],
                            },
                            dst_pinned_node: {"ids": [dst]},
                        },
                        "edges": {
                            "e0": {
                                "subject": src_pinned_node,
                                "object": "intermediate_0"
                            },
                            "e2": {
                                "subject": "intermediate_0",
                                "object": dst_pinned_node
                            },
                        },
                    }
                }
            },
            self.bmt,
            subclass=False,
            filter_config={"max_node_degree": self.node_degree_threshold, "min_information_content": min_information_content},
            dehydrated=True,
        )
        return response

    def get_1_hop_path(self, src, dst, src_pinned_node, dst_pinned_node, min_information_content):
        response = lookup(
            self.graph,
            {
                "message": {
                    "query_graph": {
                        "nodes": {
                            src_pinned_node: {"ids": [src]},
                            dst_pinned_node: {"ids": [dst]},
                        },
                        "edges": {
                            "e0": {
                                "subject": src_pinned_node,
                                "object": dst_pinned_node
                            }
                        },
                    }
                }
            },
            self.bmt,
            subclass=False,
            dehydrated=True,
        )
        return response

    def get_node_degree(self, node_id):
        return self.degree_repo.get_node_degree(node_id)

