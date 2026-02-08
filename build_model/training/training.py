import argparse
import json
import logging
import os
import pathlib
import pickle
import random
import re
import sys
from datetime import datetime

import numpy as np
import xgboost as xgb
import matplotlib.pyplot as plt
from tqdm import tqdm

from data_loader import load_data

from constants import (node_degree_sqlite_prefix_name,
                       curie_ngd_sqlite_prefix_name,
                       node_synonymizer_sqlite_prefix_name,
                       KEGG_DATA_SOURCE,
                       DRUGBANK_TRAIN_DATA_SOURCE,
                       DRUGBANK_TEST_DATA_SOURCE)
from data_collector import DataCollector
from constants import SHUFFLED_DIR
from db_build.download_script import ensure_downloaded_and_verified


def split_data(train_percentage=0.8):
    logging.info(f"Split data to train size: {train_percentage}, and test size: {1 - train_percentage}")
    with open('./build_model/data/DrugBank_aligned_with_KG2.json', 'r') as file:
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


def drugbank_data(data_source):
    if data_source == DRUGBANK_TRAIN_DATA_SOURCE:
        with open('./build_model/data/training.json', 'r') as file:
            data = json.load(file)
    else:
        with open('./build_model/data/testing.json', 'r') as file:
            data = json.load(file)
    training = []
    for key, value in data.items():
        related_CURIE = set()

        batch_of_nodes = [k for k in value["indication_NER_aligned"].keys()]
        batch_of_nodes.extend([k for k in value["mechanistic_intermediate_nodes"].keys()])

        related_CURIE.add(key)
        related_CURIE.update(batch_of_nodes)

        for rel in related_CURIE:
            training.append((rel, related_CURIE))

    return training


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
    else:
        raise ValueError(f"Data source does not exist: {data_source}")


def train(x, y, group, kg_version):
    logging.info("Training started")
    dtrain = xgb.DMatrix(x, label=y)
    dtrain.set_group(group)
    params = {  # hyperparameters extracted from the last hyperparameter-tuning.log
        'objective': 'rank:pairwise',
        'eval_metric': 'ndcg',
        'eta': 0.24,
        'max_depth': 10,
        'subsample': 0.91,
        'colsample_bytree': 0.84,
        'min_child_weight': 8,
        'gamma': 3.87
    }
    bst = xgb.train(params, dtrain, num_boost_round=200)
    bst.save_model(f"pathfinder_xgboost_model_kg_{kg_version}")
    logging.info("Training finished")


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


def train_all(output_dir, kg_version):
    x_k, y_k, group_k = load_data(output_dir, KEGG_DATA_SOURCE, shuffled=False)
    x_d, y_d, group_d = load_data(output_dir, DRUGBANK_TRAIN_DATA_SOURCE, shuffled=False)
    x_d_test, y_d_test, group_d_test = load_data(output_dir, DRUGBANK_TEST_DATA_SOURCE, shuffled=False)

    x = np.vstack([x_k, x_d, x_d_test])
    y = np.concatenate([y_k, y_d, y_d_test])
    group = np.concatenate([group_k, group_d, group_d_test])
    x, y, group = shuffle(x, y, group, output_dir, "All")

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
    synonymizer_dbname = f"{node_synonymizer_sqlite_prefix_name}{kg_version}.sqlite"
    out_dir = pathlib.Path(out_dir_str)

    remote_path_node_degree_db = f"~/KG{kg_version}/{node_degree_dbname}"
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

    remote_path_synonymizer_db = f"~/KG{kg_version}/{synonymizer_dbname}"
    local_path_synonymizer_db = out_dir / synonymizer_dbname
    ensure_downloaded_and_verified(
        host=host,
        username=username,
        port=port,
        remote_path=remote_path_synonymizer_db,
        local_path=local_path_synonymizer_db,
        key_path=key_path,
        password=password,
    )

    remote_path_curie_ngd_db = f"~/KG{kg_version}/{curie_ngd_dbname}"
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


def kg_version_validator(value: str) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise argparse.ArgumentTypeError("KG version must look like X.Y.Z (e.g. 2.10.2)")
    return value


def parse_args():
    parser = argparse.ArgumentParser(
        description="Training expander model to rank neighbors."
    )

    parser.add_argument(
        "--kg-version",
        type=kg_version_validator,
        required=True,
        metavar="VERSION",
        help="Knowledge graph version (e.g. 2.10.2)",
    )

    parser.add_argument(
        "--plover-url",
        type=str,
        required=True,
        help="PloverDB URL",
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

    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info(f"Start time: {datetime.now()}")
    args = parse_args()
    kg_version = args.kg_version
    download_databases(
        kg_version=kg_version,
        host=args.db_host,
        username=args.db_username,
        port=args.db_port,
        key_path=args.ssh_key,
        password=args.ssh_password or os.getenv("SSH_PASSWORD"),
        out_dir_str=args.out_dir
    )
    # split_data()

    data_source = DRUGBANK_TEST_DATA_SOURCE
    input_data = create_training_data(data_source)
    DataCollector(kg_version, args.plover_url, args.out_dir, os.path.join(args.out_dir, data_source)).gather_data(
        input_data)

    train_all(args.out_dir, kg_version)
