import logging
import os
import pickle

from pathfinder.core.repo.NodeDegreeRepo import NodeDegreeRepo

from constants import (node_degree_sqlite_prefix_name,
                       node_synonymizer_sqlite_prefix_name)
from node_synonymizer import NodeSynonymizer


class FeatureStructure:

    def __init__(self, kg_version, db_directory, biolink_helper):
        self.node_degree_repo = NodeDegreeRepo(
            os.path.join(db_directory, f"{node_degree_sqlite_prefix_name}{kg_version}.sqlite"))
        self.node_synonymizer = NodeSynonymizer(
            os.path.join(db_directory, f"{node_synonymizer_sqlite_prefix_name}{kg_version}.sqlite"))
        self.biolink_helper = biolink_helper

        self.degree_category_to_idx = self.get_degree_category_to_idx()
        self.edge_category_to_idx = self.load_edge_category_to_idx()
        self.ancestors_by_indices = self.get_ancestors_by_indices(self.edge_category_to_idx)
        self.category_to_idx, self.sorted_category_list = self.get_category_to_idx()

        self.save_to_file()

    def save_to_file(self):
        with open(f"src/pathfinder/resources/ancestors_by_indices.pkl", "wb") as f:
            pickle.dump(self.ancestors_by_indices, f)
        with open(f"src/pathfinder/resources/sorted_category_list.pkl", "wb") as f:
            pickle.dump(self.sorted_category_list, f)
        with open(f"src/pathfinder/resources/node_degree_category_by_indices.pkl", "wb") as f:
            pickle.dump(self.degree_category_to_idx, f)
        with open(f"src/pathfinder/resources/edge_category_to_idx.pkl", "wb") as f:
            pickle.dump(self.degree_category_to_idx, f)

    def get_degree_category_to_idx(self):
        logging.info("get degree category to idx")
        degree_categories = self.node_degree_repo.get_degree_categories()
        sorted_degree_category = sorted(list(degree_categories))
        logging.info("get degree category to idx finished")
        return {cat_name: idx for idx, cat_name in enumerate(sorted_degree_category)}

    def load_edge_category_to_idx(self):
        all_predicates = self.biolink_helper.get_descendants("biolink:related_to")
        all_predicates.sort()
        return {cat_name: idx for idx, cat_name in enumerate(all_predicates)}

    def get_ancestors_by_indices(self, edge_category_to_idx):
        logging.info("get ancestors by indices")
        ancestors_by_indices = {}

        for key, value in edge_category_to_idx.items():
            ancestors = self.biolink_helper.get_ancestors(key)
            indices_of_ancestors = []
            for ancestor in ancestors:
                if ancestor in edge_category_to_idx:
                    indices_of_ancestors.append(edge_category_to_idx[ancestor])
            ancestors_by_indices[value] = indices_of_ancestors
        logging.info("get ancestors by indices finished")
        return ancestors_by_indices

    def get_category_to_idx(self):
        logging.info("get category to idx")
        category_list = self.node_synonymizer.get_distinct_category_list()
        sorted_category_list = sorted(category_list)
        logging.info("get category to idx finished")
        return {cat_name: idx for idx, cat_name in enumerate(sorted_category_list)}, sorted_category_list
