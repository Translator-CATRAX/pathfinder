import logging

import numpy as np
import optuna
import xgboost as xgb
from sklearn.metrics import ndcg_score

from data_loader import load_data
from label_generator import binary_labels_to_importance_labels_converter


def split_with_group(group, x, y):
    training_size = int(len(group) * 0.9)
    x_training_size = 0
    for i in range(0, training_size, 1):
        x_training_size += group[i]

    return (x[: x_training_size],
            x[x_training_size:],
            y[: x_training_size],
            y[x_training_size:],
            group[:training_size],
            group[training_size:])

def exp01(x, k=5.0):
    return (np.exp(k * x) - 1) / (np.exp(k) - 1)

def tune_hyperparameters(output_dir, data_source):
    x, y, group = load_data(output_dir, data_source, True)
    y = binary_labels_to_importance_labels_converter(x, y)

    X_train, X_valid, y_train, y_valid, group_train, group_valid = split_with_group(group, x, y)

    def objective(trial):
        logging.info("objective")
        params = {
            'objective': 'rank:pairwise',
            'eval_metric': 'ndcg',
            'eta': trial.suggest_float('eta', 0.01, 0.3, log=True),
            'max_depth': trial.suggest_int('max_depth', 3, 10),
            'subsample': trial.suggest_float('subsample', 0.6, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
            'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
            'gamma': trial.suggest_float('gamma', 0, 5)
        }

        dtrain = xgb.DMatrix(X_train, label=y_train)
        dvalid = xgb.DMatrix(X_valid, label=y_valid)

        dtrain.set_group(group_train)
        dvalid.set_group(group_valid)

        bst = xgb.train(params, dtrain, num_boost_round=400,
                        evals=[(dvalid, 'validation')],
                        early_stopping_rounds=20, verbose_eval=False)

        preds = bst.predict(dvalid)
        score = ndcg_score([y_valid], [preds])

        return score

    study = optuna.create_study(direction='maximize')
    study.optimize(objective, n_trials=50)

    logging.info(f"Best params: {study.best_params}")
    logging.info(f"Best NDCG score: {study.best_value}")
