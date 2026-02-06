import logging
import os
import pickle

import numpy as np

from constants import SHUFFLED_DIR


def load_data(output_dir, data_source, shuffled = True):
    if shuffled:
        directory = os.path.join(output_dir, data_source, SHUFFLED_DIR)
    else:
        directory = os.path.join(output_dir, data_source)
    logging.info(f"Features vector is loading")
    x = np.load(os.path.join(directory, "X_data.npy"))
    logging.info(f"Features vector is loaded")
    logging.info(f"Labels are loading")
    y = np.load(os.path.join(directory, "y_data.npy"))
    logging.info(f"Labels are loaded")
    with open(os.path.join(directory, "group.pkl"), "rb") as f:
        group = pickle.load(f)

    return x, y, group
