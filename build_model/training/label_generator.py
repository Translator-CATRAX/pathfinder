import logging
import csv

import numpy as np
from pathfinder.core.feature_extractor import get_edge_categories_start_end_index

def exp_func(weight, k=5.0):
    return (np.exp(k * weight) - 1) / (np.exp(k) - 1)


def save_predicate_weights(expo, edge_category_to_idx):
    with open("new_graph_predicate_weights.csv", mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Predicate", "IDF weight"])
        for category, index in edge_category_to_idx.items():
            writer.writerow([category, expo[index]])


def load_id_edge_weight_of_KG2(edge_category_to_idx):
    my_dict = {}

    with open("KG2_graph_predicate_weights.csv", mode="r") as file:
        reader = csv.reader(file)

        # Skip the header row
        next(reader)

        for row in reader:
            key = row[0]
            value = float(row[1])
            my_dict[key] = value

        pairs = [(key, value) for key, value in edge_category_to_idx.items()]
        sorted_pairs = sorted(pairs, key=lambda x: x[1], reverse=False)
        percents = []
        for category, index in sorted_pairs:
            if my_dict[category] == 1.0:
                percents.append(0)
            else:
                percents.append(my_dict[category])

        return np.array(percents)



def idf_weights(features, labels, start, end):
    x_chunk = []
    counter = 0
    for i in range(len(features)):
        if labels[i] == 1:
            x_chunk.append(features[i, start:end])
            counter += 1

    x_chunk = np.array(x_chunk)

    column_sums = np.sum(x_chunk == 1, axis=0)
    return (counter - column_sums)/counter



def binary_labels_to_importance_labels_converter(features, labels, feature_structure):
    start, end = get_edge_categories_start_end_index(len(feature_structure.category_to_idx), len(feature_structure.edge_category_to_idx))

    # kg2 weights results in a better model so we still use kg2 predicates weights and not using:
    # percents = idf_weights(features, labels, start, end)
    percents = load_id_edge_weight_of_KG2(feature_structure.edge_category_to_idx)
    expo = exp_func(percents, 3)

    new_labels = []
    counter_removed = 0
    counter = 0
    for i in range(len(features)):
        if labels[i] == 1:
            label = np.dot(features[i, start:end], expo)
            if label > 0.9:
                new_labels.append(label)
                counter += 1
            else:
                new_labels.append(0)
                counter_removed += 1
        else:
            new_labels.append(0)

    logging.info(f"counter: {counter}")
    logging.info(f"counter_removed: {counter_removed}")
    logging.info(f"retained/removed ratio: {counter/counter_removed}")

    return np.array(new_labels)