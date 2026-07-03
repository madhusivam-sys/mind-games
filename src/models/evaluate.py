from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, precision_score, recall_score


@dataclass(slots=True)
class EvaluationReport:
    accuracy: float
    precision: float
    recall: float
    confusion: list[list[int]]
    feature_importance: dict[str, float]


def evaluate_classifier(model: object, x_test: pd.DataFrame, y_test: pd.Series) -> EvaluationReport:
    predictions = model.predict(x_test)
    importance = getattr(model, "feature_importances_", None)
    if importance is None:
        coefficients = getattr(model, "coef_", None)
        importance_values = coefficients[0] if coefficients is not None else [0.0 for _ in x_test.columns]
    else:
        importance_values = importance
    return EvaluationReport(
        accuracy=float(accuracy_score(y_test, predictions)),
        precision=float(precision_score(y_test, predictions, zero_division=0)),
        recall=float(recall_score(y_test, predictions, zero_division=0)),
        confusion=confusion_matrix(y_test, predictions).tolist(),
        feature_importance={column: float(value) for column, value in zip(x_test.columns, importance_values, strict=False)},
    )
