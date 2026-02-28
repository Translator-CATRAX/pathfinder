import logging

import numpy as np

def exp_func(weight, k=5.0):
    return (np.exp(k * weight) - 1) / (np.exp(k) - 1)

def binary_labels_to_importance_labels_converter(features, labels):
    start, end = 60, 303

    x_chunk = []
    counter = 0
    for i in range(len(features)):
        if labels[i] == 1:
            x_chunk.append(features[i, start:end])
            counter += 1

    x_chunk = np.array(x_chunk)

    column_sums = np.sum(x_chunk == 1, axis=0)
    percents = (counter - column_sums)/counter
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

    return np.array(new_labels)