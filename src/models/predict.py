from __future__ import annotations

import numpy as np
import pandas as pd

from models.registry import load_model_artifact


def predict_frame(model_name: str, feature_frame: pd.DataFrame) -> pd.Series:
    payload = load_model_artifact(model_name)
    model = payload["model"]
    feature_columns = payload["feature_columns"]
    probabilities = model.predict_proba(feature_frame[feature_columns].fillna(0.0))
    classes = getattr(model, "classes_", np.array([0, 1]))
    if probabilities.shape[1] == 1:
        positive_probability = np.ones(len(feature_frame)) if int(classes[0]) == 1 else np.zeros(len(feature_frame))
    else:
        positive_index = int(np.where(classes == 1)[0][0]) if 1 in classes else 1
        positive_probability = probabilities[:, positive_index]
    return pd.Series(positive_probability, index=feature_frame.index, name=f"{model_name}_probability")
