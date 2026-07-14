from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from utils.config import get_paths

DEMO_MODEL_STATUS = "demo_only"
DEMO_MODEL_NOTICE = (
    "Experimental baseline trained on the bundled sample dataset; not calibrated for trading use."
)


def demo_artifact_metadata() -> dict[str, str]:
    return {
        "status": DEMO_MODEL_STATUS,
        "training_source": "data/samples/nifty_futures_sample.csv",
        "validation": "small chronological holdout",
        "notice": DEMO_MODEL_NOTICE,
    }


def model_dir() -> Path:
    path = get_paths().model_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_model_artifact(name: str, artifact: Any) -> Path:
    destination = model_dir() / f"{name}.pkl"
    with destination.open("wb") as handle:
        pickle.dump(artifact, handle)
    return destination


def load_model_artifact(name: str) -> Any:
    with (model_dir() / f"{name}.pkl").open("rb") as handle:
        return pickle.load(handle)
