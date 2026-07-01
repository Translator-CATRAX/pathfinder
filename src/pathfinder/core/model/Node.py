from __future__ import annotations
import pickle


class Node:

    def __init__(self, curie: str, name: str="", degree: float=1, category: str="") -> None:
        self.id = curie
        self.name = name
        self.degree = degree
        self.category = category

    def __eq__(self, other: Node) -> bool:
        if isinstance(other, Node):
            return self.id == other.id
        return False

    def __str__(self) -> str:
        return self.id

    def __hash__(self) -> int:
        return hash(str(self))

    def serialize(self) -> bytes:
        return pickle.dumps(self)

    @staticmethod
    def deserialize(data: bytes) -> Node:
        return pickle.loads(data)

    def __copy__(self) -> Node:
        return Node(self.id, self.name, self.degree, self.category)

    def __deepcopy__(self, memo: dict) -> Node:
        return Node(self.id, self.name, self.degree, self.category)
