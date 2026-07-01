class PathListToGraphConverter:

    def __init__(self, source_node_name, destination_node_name):
        self.source_node_name = source_node_name
        self.destination_node_name = destination_node_name
        self.counter_to_generate_new_node_name = 0
        self.counter_to_generate_new_edge_name = 0
        self.node_name = "n00_"
        self.edge_name = "e00_"

    def generate_new_node_name(self):
        self.counter_to_generate_new_node_name += 1
        return f"{self.node_name}{self.counter_to_generate_new_node_name}"

    def generate_new_edge_name(self):
        self.counter_to_generate_new_edge_name += 1
        return f"{self.edge_name}{self.counter_to_generate_new_edge_name}"

    def convert(self, paths):
        nodes = {}
        edges = {}
        for path in paths:
            if len(path.edges) == 0:
                continue
            for i, edge in enumerate(path.edges):
                if i == 0:
                    if edge.source.id not in nodes:
                        nodes[edge.source.id] = self.source_node_name
                if i == len(path.edges) - 1:
                    if edge.target.id not in nodes:
                        nodes[edge.target.id] = self.destination_node_name
                if edge.source.id not in nodes:
                    nodes[edge.source.id] = self.generate_new_node_name()
                if edge.target.id not in nodes:
                    nodes[edge.target.id] = self.generate_new_node_name()
                edge_exist = False
                for key, e in edges.items():
                    if (e[0] == nodes[edge.source.id] and e[1] == nodes[edge.target.id]) \
                            or (e[1] == nodes[edge.source.id] and e[0] == nodes[edge.target.id]):
                        edge_exist = True
                if not edge_exist:
                    edges[self.generate_new_edge_name()] = (nodes[edge.source.id], nodes[edge.target.id])
        nodes = {value: key for key, value in nodes.items()}
        return nodes, edges
