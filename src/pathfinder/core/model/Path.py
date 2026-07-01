from __future__ import annotations

import copy
import math
import pickle
import statistics

from pathfinder.core.model.Node import Node
from pathfinder.core.model.Edge import Edge


class Path:

    def __init__(self, path_limit: int, edges: list[Edge] | None = None, node: Node = None) -> None:
        self.path_limit = path_limit
        self.edges = edges if edges is not None else []
        self.node = node

    def __copy__(self):
        cls = self.__class__
        new_path = cls.__new__(cls)

        new_path.path_limit = self.path_limit
        new_path.edges = copy.copy(self.edges)
        new_path.node = copy.copy(self.node)

        return new_path

    def __deepcopy__(self, memo):
        cls = self.__class__
        new_path = cls.__new__(cls)

        memo[id(self)] = new_path

        new_path.path_limit = self.path_limit
        new_path.edges = copy.deepcopy(self.edges, memo)
        new_path.node = copy.deepcopy(self.node, memo)

        return new_path

    @classmethod
    def from_nodes(cls, path_limit: int, nodes: list[Node]) -> Path:
        edges = []
        if len(nodes) < 2:
            raise Exception("Path must have at least 2 nodes.")
        for i in range(0, len(nodes) - 1):
            edges.append(Edge(nodes[i], nodes[i + 1], None, None))
        return cls(path_limit, edges=edges)

    @classmethod
    def from_curie(cls, path_limit: int, node: Node) -> Path:
        return cls(path_limit, edges=[], node=node)

    def __eq__(self, other: Path) -> bool:
        if isinstance(other, Path):
            return str(self) == str(other)
        return False

    def __hash__(self) -> int:
        return hash(str(self))

    def __str__(self) -> str:
        result = ""
        for i, edge in enumerate(self.edges):
            if i == len(self.edges) - 1:
                result += str(edge)
            else:
                result += str(edge) + " | "
        return result

    def calculate_degree_penalty(self, degrees, p) -> float:
        if not degrees:
            return 0
        sum_of_powers = sum(d ** p for d in degrees)
        mean_of_powers = sum_of_powers / len(degrees)
        penalty = mean_of_powers ** (1 / p)

        return penalty

    def compute_weight(self) -> float:
        if len(self.edges) == 0:
            return 0
        if len(self.edges) == 1:
            return 1
        weight_over_degree = []
        weight = []
        degree = []
        for i, edge in enumerate(self.edges):
            edge_weight = edge.compute_weight()
            if edge_weight is None:
                return 0
            if edge.target.degree > 0 and i != len(self.edges) - 1:
                degree.append(edge.target.degree)
            if edge_weight < 1:
                weight.append(edge_weight)
                if edge.target.degree > 1 and i != len(self.edges) - 1:
                    weight_over_degree.append(edge_weight / math.log(edge.target.degree))
                else:
                    weight_over_degree.append(edge_weight)

        w_d_geo_mean = statistics.geometric_mean(weight_over_degree)
        w_geo_mean = statistics.geometric_mean(weight)

        # if len(degree) > 0:
        #     degree_penalty = self.calculate_degree_penalty(degree, 4)
        #     if degree_penalty > 1:
        #         w_geo_mean /= math.log(degree_penalty)

        return w_geo_mean

    def make_new_path(self, last_edge, path_limit=None) -> Path:
        new_path = copy.deepcopy(self)
        new_path.edges.append(last_edge)

        if path_limit is not None:
            new_path.path_limit = path_limit
        else:
            new_path.path_limit = self.path_limit - 1

        return new_path

    def last_curie(self) -> str:
        if len(self.edges) == 0 and self.node is None:
            raise Exception("Path is empty.")
        if len(self.edges) == 0 and self.node:
            return self.node.id
        return self.edges[-1].target.id

    def node_set(self) -> set[Node]:
        node_set = set()
        for edge in self.edges:
            node_set.add(edge.source)
            node_set.add(edge.target)
        return node_set

    def node_list(self) -> list[Node]:
        node_list = []
        for i, edge in enumerate(self.edges):
            if i == 0:
                node_list.append(edge.source)
            node_list.append(edge.target)
        return node_list

    def serialize(self) -> bytes:
        return pickle.dumps(self)

    @staticmethod
    def deserialize(data) -> Path:
        return pickle.loads(data)