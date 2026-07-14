from __future__ import annotations

from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier

from features.feature_store import load_sample_features
from labels.reversal_labels import label_reversal_success
from models.evaluate import EvaluationReport, evaluate_classifier
from models.registry import demo_artifact_metadata, save_model_artifact
from models.train_breakout_model import FEATURE_COLUMNS


def train_reversal_model() -> EvaluationReport:
    frame = load_sample_features()
    labels = label_reversal_success(frame)
    frame["target"] = labels["reversal_success"].astype(int)
    features = frame[FEATURE_COLUMNS].fillna(0.0)
    date_mask = frame["session_date"].isin(frame["session_date"].drop_duplicates().tolist()[-1:])
    x_train, x_test = features.loc[~date_mask], features.loc[date_mask]
    y_train, y_test = frame["target"].loc[~date_mask], frame["target"].loc[date_mask]
    if x_train.empty or x_test.empty:
        split_index = max(len(features) - 4, 1)
        x_train, x_test = features.iloc[:split_index], features.iloc[split_index:]
        y_train, y_test = frame["target"].iloc[:split_index], frame["target"].iloc[split_index:]
    if y_train.nunique() < 2:
        model = DummyClassifier(strategy="constant", constant=int(y_train.iloc[0]))
    else:
        model = RandomForestClassifier(n_estimators=100, max_depth=4, random_state=42)
    model.fit(x_train, y_train)
    report = evaluate_classifier(model, x_test, y_test)
    save_model_artifact(
        "reversal_model",
        {
            "model": model,
            "feature_columns": list(x_train.columns),
            "report": report,
            "metadata": demo_artifact_metadata(),
        },
    )
    return report


if __name__ == "__main__":
    print(train_reversal_model())
