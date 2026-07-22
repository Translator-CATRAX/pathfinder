import json
import requests


class RetrieverRepo:

    def __init__(self, node_degree_threshold, retriever_path, degree_repo):
        self.node_degree_threshold = node_degree_threshold
        self.degree_repo = degree_repo
        self.retriever_path = retriever_path

    def get_neighbors_with_edges(self, curie):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        payload = {
            "message": {
                "query_graph": {
                    "nodes": {
                        "n1": {"ids": [curie]},
                        "n2": {"categories": ["biolink:NamedThing"]},
                    },
                    "edges": {"e1": {"subject": "n1", "object": "n2"}},
                }
            },
            "parameters": {
                "subclass": False,
                "dehydrated": True,
                "filter_config": {"max_node_degree": self.node_degree_threshold},
                "tier": 0
            }
        }

        try:
            res = requests.post(
                self.retriever_path, headers=headers, json=payload, timeout=200
            )
            res.raise_for_status()
            response = res.json()

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
                nodes[neighbor_id]['category'] = \
                    response['message']['knowledge_graph']['nodes'][neighbor_id]['categories'][
                        0]
                if neighbor_id not in edges:
                    edges[neighbor_id] = [info['predicate']]
                else:
                    edges[neighbor_id].append(info['predicate'])
            if curie in response['message']['knowledge_graph']['nodes']:
                return response['message']['knowledge_graph']['nodes'][curie]['name'], \
                    response['message']['knowledge_graph']['nodes'][curie]['categories'][0], nodes, edges, response['message']['knowledge_graph']
            return None, None, None, None, response['message']['knowledge_graph']

        except requests.exceptions.HTTPError as http_err:
            error_msg = f"HTTP error occurred for Curie: {curie}: {http_err}"
            if res.text:
                error_msg += f" | Error details: {res.text}"
            raise RuntimeError(error_msg) from http_err
        except requests.exceptions.ConnectionError as conn_err:
            raise RuntimeError(f"Connection error occurred: {conn_err}") from conn_err
        except requests.exceptions.Timeout as timeout_err:
            raise RuntimeError(f"Timeout error occurred: {timeout_err}") from timeout_err
        except requests.exceptions.RequestException as req_err:
            raise RuntimeError(f"An unexpected error occurred: {req_err}") from req_err
        except json.JSONDecodeError as json_err:
            raise RuntimeError(f"Failed to parse the response as JSON. Raw response: {res.text}") from json_err

    def get_3_hops_paths(self, src, dst, src_pinned_node, dst_pinned_node, min_information_content):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        payload = {
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
            },
            "parameters": {
                "subclass": False,
                "dehydrated": True,
                "filter_config": {"max_node_degree": self.node_degree_threshold,
                                  "min_information_content": min_information_content},
                "tier": 0
            }
        }

        try:
            res = requests.post(
                self.retriever_path, headers=headers, json=payload, timeout=100
            )
            res.raise_for_status()
            return res.json()

        except requests.exceptions.HTTPError as http_err:
            error_msg = f"HTTP error occurred: {http_err}"
            if res.text:
                error_msg += f" | Error details: {res.text}"
            raise RuntimeError(error_msg) from http_err
        except requests.exceptions.ConnectionError as conn_err:
            raise RuntimeError(f"Connection error occurred: {conn_err}") from conn_err
        except requests.exceptions.Timeout as timeout_err:
            raise RuntimeError(f"Timeout error occurred: {timeout_err}") from timeout_err
        except requests.exceptions.RequestException as req_err:
            raise RuntimeError(f"An unexpected error occurred: {req_err}") from req_err
        except json.JSONDecodeError as json_err:
            raise RuntimeError(f"Failed to parse the response as JSON. Raw response: {res.text}") from json_err

    def get_2_hops_paths(self, src, dst, src_pinned_node, dst_pinned_node, min_information_content):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        payload = {
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
            },
            "parameters": {
                "subclass": False,
                "dehydrated": True,
                "filter_config": {"max_node_degree": self.node_degree_threshold,
                                  "min_information_content": min_information_content},
                "tier": 0
            }
        }

        try:
            res = requests.post(
                self.retriever_path, headers=headers, json=payload, timeout=30
            )
            res.raise_for_status()
            return res.json()

        except requests.exceptions.HTTPError as http_err:
            error_msg = f"HTTP error occurred: {http_err}"
            if res.text:
                error_msg += f" | Error details: {res.text}"
            raise RuntimeError(error_msg) from http_err
        except requests.exceptions.ConnectionError as conn_err:
            raise RuntimeError(f"Connection error occurred: {conn_err}") from conn_err
        except requests.exceptions.Timeout as timeout_err:
            raise RuntimeError(f"Timeout error occurred: {timeout_err}") from timeout_err
        except requests.exceptions.RequestException as req_err:
            raise RuntimeError(f"An unexpected error occurred: {req_err}") from req_err
        except json.JSONDecodeError as json_err:
            raise RuntimeError(f"Failed to parse the response as JSON. Raw response: {res.text}") from json_err

    def get_1_hop_path(self, src, dst, src_pinned_node, dst_pinned_node, min_information_content):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        payload = {
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
            },
            "parameters": {
                "subclass": False,
                "dehydrated": True,
                "filter_config": {"max_node_degree": self.node_degree_threshold,
                                  "min_information_content": min_information_content},
                "tier": 0
            }
        }

        try:
            res = requests.post(
                self.retriever_path, headers=headers, json=payload, timeout=30
            )
            res.raise_for_status()
            return res.json()

        except requests.exceptions.HTTPError as http_err:
            error_msg = f"HTTP error occurred: {http_err}"
            if res.text:
                error_msg += f" | Error details: {res.text}"
            raise RuntimeError(error_msg) from http_err
        except requests.exceptions.ConnectionError as conn_err:
            raise RuntimeError(f"Connection error occurred: {conn_err}") from conn_err
        except requests.exceptions.Timeout as timeout_err:
            raise RuntimeError(f"Timeout error occurred: {timeout_err}") from timeout_err
        except requests.exceptions.RequestException as req_err:
            raise RuntimeError(f"An unexpected error occurred: {req_err}") from req_err
        except json.JSONDecodeError as json_err:
            raise RuntimeError(f"Failed to parse the response as JSON. Raw response: {res.text}") from json_err

    def get_node_degree(self, node_id):
        return self.degree_repo.get_node_degree(node_id)
