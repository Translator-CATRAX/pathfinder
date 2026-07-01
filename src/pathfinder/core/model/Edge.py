import copy
from pathfinder.core.model.Node import Node


class Edge:
    def __init__(self, source: Node, target: Node, weight: float, weight_bar: float) -> None:
        self.source = source
        self.target = target
        self.weight = weight
        self.weight_bar = weight_bar

    def compute_weight(self):
        if self.weight_bar is None and self.weight is None:
            return None
        if self.weight_bar is None:
            return self.weight
        if self.weight is None:
            return self.weight_bar
        return (self.weight + self.weight_bar) / 2

    def __str__(self) -> str:
        return f"{self.source} -> {self.target}"

    def __copy__(self):
        cls = self.__class__
        result = cls.__new__(cls)
        result.__dict__.update(self.__dict__)
        return result

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, copy.deepcopy(v, memo))

        return result

    def __eq__(self, other):
        if isinstance(other, Node):
            return str(self) == str(other)
        return False

    def __hash__(self) -> int:
        return hash(str(self))
