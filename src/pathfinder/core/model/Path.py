import math
import pickle
import statistics

from pathfinder.core.model.Node import Node


class Path:

    def __init__(self, path_limit, links=None):
        if links is None:
            links = list()
        self.path_limit = path_limit
        self.links = links

    def __eq__(self, other):
        if isinstance(other, Path):
            return str(self) == str(other)
        return False

    def __hash__(self):
        return hash(str(self))

    def __str__(self):
        result = ""
        for link in self.links:
            result += str(link)
        return result

    def calculate_degree_penalty(self, degrees, p):
        if not degrees:
            return 0
        sum_of_powers = sum(d ** p for d in degrees)
        mean_of_powers = sum_of_powers / len(degrees)
        penalty = mean_of_powers ** (1 / p)

        return penalty

    def compute_weight(self):
        weight_over_degree = []
        weight = []
        degree = []
        for link in self.links:
            if link.weight is None:
                return 0
            if link.degree > 0:
                degree.append(link.degree)
            if link.weight < 1:
                weight.append(link.weight)
                if link.degree > 0:
                    weight_over_degree.append(link.weight / math.log(link.degree))
                else:
                    weight_over_degree.append(link.weight)

        w_d_geo_mean = statistics.geometric_mean(weight_over_degree)
        w_geo_mean = statistics.geometric_mean(weight_over_degree)

        if len(degree) > 0:
            degree_penalty = self.calculate_degree_penalty(degree, 4)
            w_geo_mean /= math.log(degree_penalty)

        return (w_d_geo_mean + w_geo_mean) / 2

    def make_new_path(self, last_link, path_limit=None):
        new_links = [Node(link.id, link.weight, link.name, link.degree, link.category) for link in self.links]
        new_links.append(last_link)
        if path_limit is not None:
            limit = path_limit
        else:
            limit = self.path_limit - 1
        return Path(limit, new_links)

    def last(self):
        if len(self.links) == 0:
            raise Exception("Path is empty.")
        return self.links[-1]

    def path_src_to_id(self, id):
        new_links = []
        for link in self.links:
            new_links.append(Node(link.id, link.weight, link.name, link.degree, link.category))
            if link.id == id:
                break
        return Path(len(new_links) - 1, new_links)

    def path_id_to_dest(self, id):
        new_links = []
        for link in reversed(self.links):
            new_links.append(Node(link.id, link.weight, link.name, link.degree, link.category))
            if link.id == id:
                break
        new_links.reverse()
        return Path(len(new_links) - 1, new_links)

    def serialize(self):
        return pickle.dumps(self)

    @staticmethod
    def deserialize(data):
        return pickle.loads(data)
