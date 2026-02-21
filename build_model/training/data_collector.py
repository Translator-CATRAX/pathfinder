import logging
import os
import pickle
from pathlib import Path

import numpy as np
from pathfinder.core.feature_extractor import get_category
from pathfinder.core.feature_extractor import get_neighbors_info
from pathfinder.core.feature_extractor import get_np_array_features
from pathfinder.core.repo.NGDRepository import NGDRepository
from pathfinder.core.repo.NodeDegreeRepo import NodeDegreeRepo
from pathfinder.core.repo.PloverDBRepo import PloverDBRepo
from tqdm import tqdm

from constants import (node_degree_sqlite_prefix_name,
                       curie_ngd_sqlite_prefix_name,
                       node_synonymizer_sqlite_prefix_name)
from node_synonymizer import NodeSynonymizer


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

    def gather_data(self, input_data, feature_structure):

        pbar = tqdm(
            total=len(input_data),
            desc="Collecting data",
            unit="Test data",
            dynamic_ncols=True
        )
        counter, group, curie, curies, y, x_list = self.partial_load()
        pbar.update(counter)
        for key_nodes_pair in input_data[counter:len(input_data)]:
            pbar.set_postfix(
                current=key_nodes_pair[0],
                status=f"neighbors length: loading"
            )
            try:
                content_by_curie, curie_category = get_neighbors_info(
                    key_nodes_pair[0],
                    self.ngd_repo,
                    self.plover_repo,
                    self.node_degree_repo
                )
            except Exception as e:
                logging.error(f"Error fetching neighbors info for {key_nodes_pair[0]}: {e}")
                self.partial_save(pbar.n, group, curie, curies, y, x_list)
                raise e
            if content_by_curie is None:
                pbar.set_postfix(
                    current=key_nodes_pair[0],
                    status=f"neighbors length: 0"
                )
                pbar.update(1)
                continue
            pbar.set_postfix(
                current=key_nodes_pair[0],
                status=f"neighbors length: {len(content_by_curie)}"
            )
            curie_category_onehot = get_category(curie_category.split(":")[-1], feature_structure.category_to_idx)
            group.append(len(content_by_curie))
            curie.append(key_nodes_pair[0])
            for key, value in content_by_curie.items():
                if key in key_nodes_pair[1]:
                    y.append(1)
                else:
                    y.append(0)

                curies.append(key)
                x_list.append(
                    get_np_array_features(
                        value,
                        feature_structure.category_to_idx,
                        feature_structure.edge_category_to_idx,
                        curie_category_onehot,
                        feature_structure.ancestors_by_indices,
                        feature_structure.degree_category_to_idx
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



    @staticmethod
    def partial_save(n, group, curie, curies, y, x_list):
        logging.info(f"First {n} saved in partial data to start from n")
        out_dir = Path("partial_data")
        out_dir.mkdir(exist_ok=True)

        counter_path = Path("counter.txt")
        counter_path.write_text(str(n))

        data = {
            "group": group,
            "curie": curie,
            "curies": curies,
            "y": y,
            "x_list": x_list,
        }

        for name, arr in data.items():
            with open(out_dir / f"{name}.pkl", "wb") as f:
                pickle.dump(arr, f)

    @staticmethod
    def partial_load():
        if Path("partial_data").is_dir():
            logging.info(f"Partial data found")
            counter = int(Path("counter.txt").read_text())
            with open("partial_data/group.pkl", "rb") as f:
                group = pickle.load(f)
            with open("partial_data/curie.pkl", "rb") as f:
                curie = pickle.load(f)
            with open("partial_data/curies.pkl", "rb") as f:
                curies = pickle.load(f)
            with open("partial_data/y.pkl", "rb") as f:
                y = pickle.load(f)
            with open("partial_data/x_list.pkl", "rb") as f:
                x_list = pickle.load(f)
            return counter, group, curie, curies, y, x_list
        else:
            logging.info(f"No partial data found")
            return 0, [], [], [], [], []


