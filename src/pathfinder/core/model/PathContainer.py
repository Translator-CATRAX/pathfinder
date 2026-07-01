from __future__ import annotations

from pathfinder.core.model.Path import Path


class PathContainer:

    def __init__(self):
        self.path_dict = {}

    def add_new_path(self, new_path: Path) -> None:
        if new_path.edges:
            last_edge = new_path.edges[-1]
            if last_edge.target not in self.path_dict:
                self.path_dict[last_edge.target] = []
            self.path_dict[last_edge.target].append(new_path)
        elif new_path.node:
            if new_path.node not in self.path_dict:
                self.path_dict[new_path.node] = []
            self.path_dict[new_path.node].append(new_path)
