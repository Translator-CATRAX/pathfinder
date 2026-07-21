from __future__ import annotations
import pickle
from typing import Any

import numpy as np
import xgboost as xgb
from importlib.resources import files as resource_files

from pathfinder.core.feature_extractor import get_neighbors_info, get_category, get_np_array_features, \
    get_concatenate_features, get_node_degree_feature
from pathfinder.core.model.Node import Node
from pathfinder.core.model.Edge import Edge


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


class MLRepo:

    def __init__(self, repo, degree_repo, ngd_repo):
        self.repo = repo
        self.degree_repo = degree_repo
        self.ngd_repo = ngd_repo
        self.bst_loaded = None
        self.ancestors_by_id = None
        self.category_to_idx = None
        self.edge_category_to_idx = None
        self.sorted_category_list = None
        self.node_degree_category_to_idx = None
        self.load_data()

    def load_data(self) -> None:
        pkg_files = resource_files('pathfinder.resources')
        with pkg_files.joinpath('node_degree_category_by_indices.pkl').open('rb') as f:
            self.node_degree_category_to_idx = pickle.load(f)

        with pkg_files.joinpath('sorted_category_list.pkl').open('rb') as f:
            self.sorted_category_list = pickle.load(f)

        with pkg_files.joinpath('edge_category_to_idx.pkl').open('rb') as f:
            self.edge_category_to_idx = pickle.load(f)
        self.category_to_idx = {cat_name: idx for idx, cat_name in enumerate(self.sorted_category_list)}

        with pkg_files.joinpath('ancestors_by_indices.pkl').open('rb') as f:
            self.ancestors_by_id = pickle.load(f)

        self.bst_loaded = xgb.Booster()
        self.bst_loaded.load_model(str(pkg_files.joinpath('pathfinder_xgboost_model_kg_20260408')))

    def get_edges(self, curie) -> tuple[list[Edge], dict[Any, Any]]:
        content_by_curie, curie_name, curie_category, knowledge_graph = get_neighbors_info(
            curie,
            self.ngd_repo,
            self.repo,
            self.degree_repo
        )

        if content_by_curie is None:
            return [], {}
        curie_category = curie_category.split(":")[-1] # removing the biolink: prefix
        curie_category_onehot = get_category(curie_category, self.category_to_idx)
        number_of_curie_pmid = None
        curie_pmid_dict = self.ngd_repo.get_curies_pmid_length([curie])
        if curie_pmid_dict:
            number_of_curie_pmid = curie_pmid_dict[0][1]

        degree_by_category_of_curie = self.degree_repo.get_degrees_by_node([curie])[curie]
        curie_degree_feature_array = get_node_degree_feature(
            self.node_degree_category_to_idx,
            degree_by_category_of_curie
        )

        feature_list = []
        inverse_feature_list = []
        neighbors_list = []
        neighbors_degree = []
        neighbors_name = []
        neighbors_category = []
        for key, value in content_by_curie.items():
            neighbors_list.append(key)
            neighbors_degree.append(value.get('degree_by_category', {}).get('biolink:NamedThing', 0))
            neighbors_name.append(value.get('name', ''))
            neighbors_category.append(value.get('category', ''))
            ngd_val, pmid_val, cat_onehot, edge_categories, curie_category_onehot, node_degrees_feature = get_np_array_features(
                value,
                self.category_to_idx,
                self.edge_category_to_idx,
                curie_category_onehot,
                self.ancestors_by_id,
                self.node_degree_category_to_idx
            )
            feature_list.append(
                get_concatenate_features(
                    ngd_val, pmid_val, cat_onehot, edge_categories, curie_category_onehot, node_degrees_feature
                )
            )
            inverse_feature_list.append(
                get_concatenate_features(
                    value.get('ngd'),
                    number_of_curie_pmid,
                    curie_category_onehot,
                    edge_categories,
                    cat_onehot,
                    curie_degree_feature_array
                )
            )

        feature_np = np.empty((len(feature_list) + len(inverse_feature_list), len(feature_list[0])), dtype=float)

        for i in range(len(feature_list)):
            feature_np[i] = feature_list[i]
        for i in range(len(inverse_feature_list)):
            feature_np[i + len(feature_list)] = inverse_feature_list[i]

        dtest = xgb.DMatrix(feature_np)

        scores = self.bst_loaded.predict(dtest)

        probabilities = sigmoid(scores)

        sorted_edge_list = sorted(
            zip(neighbors_list, neighbors_name, neighbors_degree, neighbors_category,
                probabilities[0:len(feature_list)], probabilities[len(feature_list):]),
            key=lambda x: (x[4] + x[5]) / 2,
            reverse=True
        )
        curie_node = Node(
            curie=curie,
            name=curie_name,
            degree=degree_by_category_of_curie['biolink:NamedThing'],
            category=curie_category
        )
        return [
            Edge(
                curie_node,
                Node(
                    curie=edge[0],
                    name=edge[1],
                    degree=edge[2],
                    category=edge[3]
                ),
                float(edge[4]),
                float(edge[5])
            ) for edge in sorted_edge_list], knowledge_graph

    def get_node_degree(self, node_id):
        return self.degree_repo.get_node_degree(node_id)
