from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from utils.config import get_paths


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
