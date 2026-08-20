import argparse
import itertools
import json
import logging
import math
import os
import pathlib
import pickle
import random
import re
import tarfile
from collections import defaultdict
from datetime import datetime

import numpy as np
import xgboost as xgb
import matplotlib.pyplot as plt
from tqdm import tqdm

from data_loader import load_data
from biolink_helper_pkg import BiolinkHelper

from constants import (node_degree_sqlite_prefix_name,
                       curie_ngd_sqlite_prefix_name,
                       gandalf_mmap_prefix_name,
                       KEGG_DATA_SOURCE,
                       DRUGBANK_DATA_SOURCE,
                       DRUGBANK_TRAIN_DATA_SOURCE,
                       DRUGBANK_TEST_DATA_SOURCE,
                       BIOLINK_VERSION)
from data_collector import DataCollector
from normalization import normalized_legacy_dataset
from feature_structure import FeatureStructure
from constants import SHUFFLED_DIR
from db_build.download_script import ensure_downloaded_and_verified


def split_data(train_percentage=0.8):
    logging.info(f"Split data to train size: {train_percentage}, and test size: {1 - train_percentage}")
    with open('./build_model/data/DrugBank_aligned_with_KG2.filtered.json', 'r') as file:
        data = json.load(file)
    items = list(data.items())

    random.shuffle(items)

    split_index = int(len(items) * train_percentage)

    dict1_items = items[:split_index]
    dict2_items = items[split_index:]

    training = dict(dict1_items)
    testing = dict(dict2_items)

    with open('./build_model/data/training.json', 'w') as file1:
        json.dump(training, file1, indent=4)

    with open('./build_model/data/testing.json', 'w') as file2:
        json.dump(testing, file2, indent=4)

    logging.info(f"Data split successfully")


def compute_pairwise_pmi(documents):
    """Computes pointwise mutual information for every pair of curies that
    co-occurs in at least one document (a document is the basket of curies
    belonging to a single drug's mechanistic pathway)."""
    n_docs = len(documents)
    doc_freq = defaultdict(int)
    pair_freq = defaultdict(int)

    for doc in documents:
        for node in doc:
            doc_freq[node] += 1
        for a, b in itertools.combinations(sorted(doc), 2):
            pair_freq[(a, b)] += 1

    pmi_scores = {}
    for (a, b), pair_count in pair_freq.items():
        p_a = doc_freq[a] / n_docs
        p_b = doc_freq[b] / n_docs
        p_ab = pair_count / n_docs
        pmi_scores[(a, b)] = math.log2(p_ab / (p_a * p_b))

    return pmi_scores


def get_pmi(pmi_scores, a, b):
    key = (a, b) if a < b else (b, a)
    return pmi_scores.get(key, 0.0)


def merge_basket(training, key, related_curies, pmi_scores):
    scored = {curie: max(get_pmi(pmi_scores, key, curie), 0.0)
              for curie in related_curies if curie != key}
    if key in training:
        training[key].update(scored)
    else:
        training[key] = scored


def drugbank_data(data_source):
    if data_source == DRUGBANK_TRAIN_DATA_SOURCE:
        with open('./build_model/data/training.json', 'r') as file:
            data = json.load(file)
    elif data_source == DRUGBANK_TEST_DATA_SOURCE:
        with open('./build_model/data/testing.json', 'r') as file:
            data = json.load(file)
    elif data_source == DRUGBANK_DATA_SOURCE:
        with open('./build_model/data/DrugBank_aligned_with_KG2.filtered.json', 'r') as file:
            data = json.load(file)
    else:
        raise ValueError(f"Data source does not exist: {data_source}")

    diseases = set()
    for key, value in data.items():
        diseases.update([k for k in value["indication_NER_aligned"].keys()])
        for mech, values in value["mechanistic_intermediate_nodes"].items():
            if values["category"] == "biolink:Disease":
                diseases.add(mech)

    entries = []
    documents = []
    for key, value in data.items():
        mechanistic_intermediate_nodes = [k for k in value["mechanistic_intermediate_nodes"].keys()]
        drug = key

        drug_nodes = set(mechanistic_intermediate_nodes) - diseases
        all_nodes = set(mechanistic_intermediate_nodes + [drug]) - diseases

        entries.append((drug, mechanistic_intermediate_nodes, drug_nodes, all_nodes))
        documents.append(all_nodes)

    # Pointwise mutual information between every pair of curies that
    # co-occur within a drug's mechanistic pathway (the basket).
    pmi_scores = compute_pairwise_pmi(documents)

    training = {}
    for drug, mechanistic_intermediate_nodes, drug_nodes, all_nodes in entries:
        merge_basket(training, drug, drug_nodes, pmi_scores)

        for mechanism in mechanistic_intermediate_nodes:
            if mechanism != drug:
                batch = all_nodes.copy()
                if mechanism in batch:
                    batch.remove(mechanism)
                merge_basket(training, mechanism, batch, pmi_scores)

    result = []

    for key, related in training.items():
        # Rank the merged basket of curies related to this key by PMI.
        sorted_related = dict(sorted(related.items(), key=lambda item: item[1], reverse=True))
        result.append((key, sorted_related))

    return result


def kegg_training_data():
    with open('./build_model/data/KEGG.json', 'r') as file:
        data = json.load(file)
    training = []
    for key, value in data.items():
        if len(value) == 0:
            continue

        related_CURIE = set()
        related_CURIE.update(value)

        for rel in related_CURIE:
            curies = set(related_CURIE)
            curies.remove(rel)
            training.append((rel, curies))

    random.seed(41)
    random.shuffle(training)

    return training


def create_training_data(data_source):
    if data_source == KEGG_DATA_SOURCE:
        return kegg_training_data()
    elif data_source == DRUGBANK_TRAIN_DATA_SOURCE:
        return drugbank_data(DRUGBANK_TRAIN_DATA_SOURCE)
    elif data_source == DRUGBANK_TEST_DATA_SOURCE:
        return drugbank_data(DRUGBANK_TEST_DATA_SOURCE)
    elif data_source == DRUGBANK_DATA_SOURCE:
        return drugbank_data(DRUGBANK_DATA_SOURCE)
    else:
        raise ValueError(f"Data source does not exist: {data_source}")


def train(x, y, group, kg_version):
    logging.info("Training started")
    dtrain = xgb.DMatrix(x, label=y)
    dtrain.set_group(group)
    params = {
        'objective': 'rank:pairwise',
        'eval_metric': 'ndcg',
        'eta': 0.1,
        'max_depth': 15,
        'subsample': 0.91,
        'colsample_bytree': 0.84,
        'min_child_weight': 1,
        'gamma': 0.1
    }
    bst = xgb.train(params, dtrain, num_boost_round=500)
    bst.save_model(f"src/pathfinder/resources/pathfinder_xgboost_model_kg_{kg_version}")
    logging.info("Training finished")


def threshold_labels(y, threshold):
    """Zeroes out any PMI label below threshold, leaving group structure
    untouched. Mirrors the old binary_labels_to_importance_labels_converter
    cutoff (label > 0.9), but applied to PMI-based labels instead of the
    predicate-weight/IDF importance score."""
    y = np.asarray(y, dtype=float).copy()
    below = y < threshold
    logging.info(f"Zeroing {int(below.sum())} of {len(y)} labels below PMI threshold {threshold}")
    y[below] = 0
    return y


def shuffle(x, y, group, output_dir, data_source):
    logging.info("Start shuffling")
    # ---- SHUFFLING BY GROUP ----

    group_start_indices = np.cumsum(np.insert(group, 0, 0))
    num_groups = len(group)

    shuffled_idx = np.random.permutation(num_groups)

    new_x_list, new_y_list, new_group_list = [], [], []

    pbar = tqdm(
        total=num_groups,
        desc="Shuffling",
        unit="data",
        dynamic_ncols=True
    )
    for g in shuffled_idx:
        s = group_start_indices[g]
        e = group_start_indices[g + 1]

        new_x_list.append(x[s:e])
        new_y_list.append(y[s:e])
        new_group_list.append(group[g])
        pbar.update(1)
    logging.info("Shuffling finished")

    x_shuffled = np.vstack(new_x_list)
    y_shuffled = np.concatenate(new_y_list)
    group_shuffled = np.array(new_group_list)

    logging.info("Converting finished")
    directory = os.path.join(output_dir, data_source, SHUFFLED_DIR)
    pathlib.Path(directory).mkdir(parents=True, exist_ok=True)
    np.save(os.path.join(directory, "X_data.npy"), x_shuffled)
    np.save(os.path.join(directory, "y_data.npy"), y_shuffled)
    with open(os.path.join(directory, "group.pkl"), "wb") as f:
        pickle.dump(group_shuffled, f)

    logging.info("Shuffled saved")

    return x_shuffled, y_shuffled, group_shuffled


def train_all_drugbank(output_dir, kg_version):
    # x_k, y_k, group_k = load_data(output_dir, KEGG_DATA_SOURCE, shuffled=False)
    x_d, y_d, group_d = load_data(output_dir, DRUGBANK_TRAIN_DATA_SOURCE, shuffled=False)
    x_d_test, y_d_test, group_d_test = load_data(output_dir, DRUGBANK_TEST_DATA_SOURCE, shuffled=False)

    x = np.vstack([x_d, x_d_test])
    y = np.concatenate([y_d, y_d_test])
    group = np.concatenate([group_d, group_d_test])
    x, y, group = shuffle(x, y, group, output_dir, DRUGBANK_DATA_SOURCE)

    train(x, y, group, kg_version)


def train_on_data_source(output_dir, data_source, kg_version):
    x, y, group = load_data(output_dir, data_source, shuffled=False)
    x, y, group = shuffle(x, y, group, output_dir, data_source)
    train(x, y, group, kg_version)


def feature_importance():
    bst_loaded = xgb.Booster()
    bst_loaded.load_model("model")
    importance_dict = bst_loaded.get_score(importance_type='cover')
    logging.info(importance_dict)
    # plot_importance(bst_loaded, importance_type='cover')
    plt.savefig("feature_importance_cover.png")

def extract_tar_gz(file_name):
    # Ensure the file exists before trying to open it
    if not os.path.exists(file_name):
        print(f"Error: The file '{file_name}' was not found.")
        return

    try:
        with tarfile.open(file_name, "r:gz") as tar:
            # Extracting all contents to the current working directory
            tar.extractall(path=".")
            print(f"Successfully extracted '{file_name}' to the current directory.")
    except Exception as e:
        print(f"An error occurred: {e}")

def download_databases(
        *,
        kg_version: str,
        host: str,
        username: str,
        port: int,
        key_path: str | None = None,
        password: str | None = None,
        out_dir_str: str
):
    node_degree_dbname = f"{node_degree_sqlite_prefix_name}{kg_version}.sqlite"
    curie_ngd_dbname = f"{curie_ngd_sqlite_prefix_name}{kg_version}.sqlite"
    out_dir = pathlib.Path(out_dir_str)

    remote_path_node_degree_db = f"~/tier0-{kg_version}/{node_degree_dbname}"
    local_path_node_degree_db = out_dir / node_degree_dbname
    ensure_downloaded_and_verified(
        host=host,
        username=username,
        port=port,
        remote_path=remote_path_node_degree_db,
        local_path=local_path_node_degree_db,
        key_path=key_path,
        password=password,
    )

    remote_path_curie_ngd_db = f"~/tier0-{kg_version}/{curie_ngd_dbname}"
    local_path_curie_ngd_db = out_dir / curie_ngd_dbname
    ensure_downloaded_and_verified(
        host=host,
        username=username,
        port=port,
        remote_path=remote_path_curie_ngd_db,
        local_path=local_path_curie_ngd_db,
        key_path=key_path,
        password=password,
    )

def parse_args():
    parser = argparse.ArgumentParser(
        description="Training expander model to rank neighbors."
    )

    parser.add_argument(
        "--kg-version",
        required=True,
        metavar="VERSION",
        help="Knowledge graph version",
    )

    parser.add_argument(
        "--db-host",
        default="arax-databases.rtx.ai",
        type=str,
        help="Database file host (default: arax-databases.rtx.ai)",
    )

    parser.add_argument(
        "--db-username",
        default="rtxconfig",
        type=str,
        help="Database file username (default: rtxconfig)",
    )

    parser.add_argument(
        "--db-port",
        default=22,
        type=int,
        help="Database file port (default: 22)",
    )

    parser.add_argument(
        "--ssh-key",
        default=None,
        help="Path to SSH private key (optional). If omitted, uses SSH agent/default keys.",
    )

    parser.add_argument(
        "--ssh-password",
        default=None,
        help="SSH password (optional; prefer key/agent). You can also set SSH_PASSWORD env var.",
    )

    # Optional: choose output dir for downloads
    parser.add_argument(
        "--out-dir",
        default=".",
        type=str,
        help="Where to store downloaded DB files (default: current directory)",
    )

    parser.add_argument(
        "--label-threshold",
        default=4,
        type=float,
        help="PMI labels below this value are zeroed out (default: 4)",
    )

    return parser.parse_args()


def get_biolink_helper():
    biolink_cache_dir = "./biolink"
    pathlib.Path(biolink_cache_dir).mkdir(parents=True, exist_ok=True)
    return BiolinkHelper(BIOLINK_VERSION, biolink_cache_dir)

class MockFeatureStructure:
    def __init__(self):
        with open(f"src/pathfinder/resources/edge_category_to_idx.pkl", "rb") as file:
            self.edge_category_to_idx = pickle.load(file)
        with open(f"src/pathfinder/resources/sorted_category_list.pkl", "rb") as file:
            self.category_to_idx = pickle.load(file)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info(f"Start time: {datetime.now()}")
    args = parse_args()
    kg_version = args.kg_version
    data_source = DRUGBANK_DATA_SOURCE
    # download_databases(
    #     kg_version=kg_version,
    #     host=args.db_host,
    #     username=args.db_username,
    #     port=args.db_port,
    #     key_path=args.ssh_key,
    #     password=args.ssh_password or os.getenv("SSH_PASSWORD"),
    #     out_dir_str=args.out_dir
    # )
    # feature_structure = FeatureStructure(kg_version, args.out_dir, get_biolink_helper())
    #
    # input_data = create_training_data(data_source)
    # input_data = normalized_legacy_dataset(input_data)
    #
    # logging.info(f"Training on {len(input_data)}")

    # DataCollector(kg_version, args.out_dir, os.path.join(args.out_dir, data_source)).gather_data(
    #     input_data, feature_structure)

    x, y, group = load_data(args.out_dir, data_source, shuffled=False)
    y = threshold_labels(y, args.label_threshold)
    x, y, group = shuffle(x, y, group, args.out_dir, data_source)

    train(x, y, group, kg_version)
