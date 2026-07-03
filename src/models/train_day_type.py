from __future__ import annotations

from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier

from labels.day_type import label_day_type
from models.evaluate import EvaluationReport, evaluate_classifier
from models.registry import save_model_artifact
from models.train_breakout_model import prepare_training_frame


def train_day_type_model() -> EvaluationReport:
    feature_frame = prepare_training_frame()
    day_type = label_day_type(feature_frame)
    merged = feature_frame.merge(day_type, on=["symbol", "session_date"], how="left")
    merged["target"] = (merged["day_type"] == "trend").astype(int)
    x_train, x_test, y_train, y_test = prepare_training_frame(include_target=True, feature_frame=merged)
    if y_train.nunique() < 2:
        model = DummyClassifier(strategy="constant", constant=int(y_train.iloc[0]))
    else:
        model = RandomForestClassifier(n_estimators=100, max_depth=4, random_state=42)
    model.fit(x_train, y_train)
    report = evaluate_classifier(model, x_test, y_test)
    save_model_artifact("day_type_model", {"model": model, "feature_columns": list(x_train.columns), "report": report})
    return report


if __name__ == "__main__":
    print(train_day_type_model())
