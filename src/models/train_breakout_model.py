from __future__ import annotations

from typing import cast

import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression

from features.feature_store import load_sample_features
from labels.breakout_labels import label_breakout_success
from models.evaluate import EvaluationReport, evaluate_classifier
from models.registry import demo_artifact_metadata, save_model_artifact

FEATURE_COLUMNS = ["distance_to_poc","distance_to_vah","distance_to_val","distance_to_vwap","aggression_score","cvd_slope","delta_slope","imbalance_cluster_count","poc_migration","breakout_through_lvn"]


def _date_split_mask(frame: pd.DataFrame) -> pd.Series:
    unique_dates = frame["session_date"].drop_duplicates().tolist()
    test_dates = unique_dates[-1:] if unique_dates else []
    return frame["session_date"].isin(test_dates)


def prepare_training_frame(include_target: bool = False, feature_frame: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series] | pd.DataFrame:
    frame = feature_frame.copy() if feature_frame is not None else load_sample_features()
    if not include_target:
        return frame
    target = cast(pd.Series, frame["target"]).astype(int)
    features = frame[FEATURE_COLUMNS].fillna(0.0)
    test_mask = _date_split_mask(frame)
    x_train, x_test = features.loc[~test_mask], features.loc[test_mask]
    y_train, y_test = target.loc[~test_mask], target.loc[test_mask]
    if x_train.empty or x_test.empty:
        split_index = max(len(features) - 4, 1)
        x_train, x_test = features.iloc[:split_index], features.iloc[split_index:]
        y_train, y_test = target.iloc[:split_index], target.iloc[split_index:]
    return x_train, x_test, y_train, y_test


def _fit_classifier(x_train: pd.DataFrame, y_train: pd.Series) -> object:
    if y_train.nunique() < 2:
        model = DummyClassifier(strategy="constant", constant=int(y_train.iloc[0]))
    else:
        model = LogisticRegression(max_iter=500)
    model.fit(x_train, y_train)
    return model


def train_breakout_model() -> EvaluationReport:
    frame = load_sample_features()
    frame["target"] = label_breakout_success(frame)
    x_train, x_test, y_train, y_test = prepare_training_frame(include_target=True, feature_frame=frame)
    model = _fit_classifier(x_train, y_train)
    report = evaluate_classifier(model, x_test, y_test)
    save_model_artifact(
        "breakout_model",
        {
            "model": model,
            "feature_columns": list(x_train.columns),
            "report": report,
            "metadata": demo_artifact_metadata(),
        },
    )
    return report


if __name__ == "__main__":
    print(train_breakout_model())
