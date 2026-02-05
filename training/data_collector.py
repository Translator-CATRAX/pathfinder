import pickle
import logging
from pathlib import Path

import numpy as np
import os
import sys

from biolink_helper_pkg import BiolinkHelper
from tqdm import tqdm

from constants import (node_degree_sqlite_prefix_name,
                       curie_ngd_sqlite_prefix_name,
                       node_synonymizer_sqlite_prefix_name,
                       BIOLINK_VERSION)
from node_synonymizer import NodeSynonymizer


from pathfinder.core.feature_extractor import get_neighbors_info
from pathfinder.core.feature_extractor import get_category
from pathfinder.core.feature_extractor import get_np_array_features
from pathfinder.core.repo.NGDRepository import NGDRepository
from pathfinder.core.repo.PloverDBRepo import PloverDBRepo
from pathfinder.core.repo.NodeDegreeRepo import NodeDegreeRepo


class DataCollector:

    def __init__(self, kg_version, plover_url, db_directory, output_directory):
        self.node_degree_repo = NodeDegreeRepo(
            os.path.join(db_directory, f"{node_degree_sqlite_prefix_name}{kg_version}.sqlite"))
        self.ngd_repo = NGDRepository(os.path.join(db_directory, f"{curie_ngd_sqlite_prefix_name}{kg_version}.sqlite"))
        self.node_synonymizer = NodeSynonymizer(
            os.path.join(db_directory, f"{node_synonymizer_sqlite_prefix_name}{kg_version}.sqlite"))
        self.output_directory = output_directory
        Path(output_directory).mkdir(parents=True, exist_ok=True)
        self.plover_repo = PloverDBRepo(plover_url, self.node_degree_repo)

    def gather_data(self, input_data):
        degree_category_to_idx = self.get_degree_category_to_idx()
        edge_category_to_idx = self.load_edge_category_to_idx()
        ancestors_by_indices = self.get_ancestors_by_indices(edge_category_to_idx)
        category_to_idx, sorted_category_list = self.get_category_to_idx()

        pbar = tqdm(
            total=len(input_data),
            desc="Collecting data",
            unit="Test data",
            dynamic_ncols=True
        )
        group = []
        curie = []
        curies = []
        y = []
        x_list = []
        for key_nodes_pair in input_data:
            content_by_curie, curie_category = get_neighbors_info(
                key_nodes_pair[0],
                self.ngd_repo,
                self.plover_repo,
                self.node_degree_repo
            )
            if content_by_curie is None:
                pbar.set_postfix(
                    current=key_nodes_pair[0],
                    status=f"neighbors length: 0"
                )
                pbar.update(1)
                continue
            curie_category_onehot = get_category(curie_category.split(":")[-1], category_to_idx)
            group.append(len(content_by_curie))
            curie.append(key_nodes_pair[0])
            pbar.set_postfix(
                current=key_nodes_pair[0],
                status=f"neighbors length: {len(content_by_curie)}"
            )
            for key, value in content_by_curie.items():
                if key in key_nodes_pair[1]:
                    y.append(1)
                else:
                    y.append(0)

                curies.append(key)
                x_list.append(
                    get_np_array_features(
                        value,
                        category_to_idx,
                        edge_category_to_idx,
                        curie_category_onehot,
                        ancestors_by_indices,
                        degree_category_to_idx
                    )
                )
            pbar.update(1)

        x = np.empty((len(x_list), len(x_list[0])), dtype=float)

        for i in range(len(x_list)):
            x[i] = x_list[i]

        np.save(f"{self.output_directory}/X_data.npy", x)
        np.save(f"{self.output_directory}/y_data.npy", y)
        with open(f"{self.output_directory}/group.pkl", "wb") as f:
            pickle.dump(group, f)
        with open(f"{self.output_directory}/curie.pkl", "wb") as f:
            pickle.dump(curie, f)
        with open(f"{self.output_directory}/curies.pkl", "wb") as f:
            pickle.dump(curies, f)
        with open(f"{self.output_directory}/ancestors_by_indices.pkl", "wb") as f:
            pickle.dump(ancestors_by_indices, f)
        with open(f"{self.output_directory}/sorted_category_list.pkl", "wb") as f:
            pickle.dump(sorted_category_list, f)
        with open(f"{self.output_directory}/node_degree_category_by_indices.pkl", "wb") as f:
            pickle.dump(degree_category_to_idx, f)

    def get_degree_category_to_idx(self):
        logging.info("get degree category to idx")
        degree_categories = self.node_degree_repo.get_degree_categories()
        sorted_degree_category = sorted(list(degree_categories))
        logging.info("get degree category to idx finished")
        return {cat_name: idx for idx, cat_name in enumerate(sorted_degree_category)}

    @staticmethod
    def get_biolink_helper():
        biolink_cache_dir = "./biolink"
        Path(biolink_cache_dir).mkdir(parents=True, exist_ok=True)
        return BiolinkHelper(BIOLINK_VERSION, biolink_cache_dir)

    @staticmethod
    def load_edge_category_to_idx():
        with open((os.path.dirname(os.path.abspath(__file__)) + '/../src/pathfinder/resources/edge_category_to_idx.pkl'),
                  "rb") as f:
            return pickle.load(f)

    def get_ancestors_by_indices(self, edge_category_to_idx):
        logging.info("get ancestors by indices")
        ancestors_by_indices = {}
        biolink_helper = self.get_biolink_helper()
        for key, value in edge_category_to_idx.items():
            ancestors = biolink_helper.get_ancestors(key)
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
