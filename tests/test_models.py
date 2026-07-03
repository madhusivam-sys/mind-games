from __future__ import annotations

from features.feature_store import load_sample_features
from models.train_breakout_model import prepare_training_frame, train_breakout_model
from models.train_day_type import train_day_type_model
from models.train_reversal_model import train_reversal_model


def test_model_training_scripts_return_reports() -> None:
    breakout = train_breakout_model()
    day_type = train_day_type_model()
    reversal = train_reversal_model()
    assert 0.0 <= breakout.accuracy <= 1.0
    assert 0.0 <= day_type.accuracy <= 1.0
    assert 0.0 <= reversal.accuracy <= 1.0


def test_training_split_prefers_session_date_boundaries() -> None:
    frame = load_sample_features()
    frame["target"] = 0
    x_train, x_test, y_train, y_test = prepare_training_frame(include_target=True, feature_frame=frame)
    assert not x_train.empty and not x_test.empty
    train_dates = set(frame.loc[x_train.index, "session_date"])
    test_dates = set(frame.loc[x_test.index, "session_date"])
    assert train_dates.isdisjoint(test_dates)
    assert len(y_train) == len(x_train)
    assert len(y_test) == len(x_test)
