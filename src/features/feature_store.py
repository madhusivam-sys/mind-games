from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from features.camarilla import CamarillaEngine
from features.cpr import CprEngine
from features.market_profile import MarketProfileEngine
from features.order_flow import OrderFlowEngine
from features.session_context import SessionContextEngine
from features.volume_profile import VolumeProfileEngine
from features.vwap import VwapEngine
from ingestion.load_csv import CsvDataLoader
from utils.config import get_paths, get_settings


@dataclass(slots=True)
class FeatureStoreBuilder:
    engines: list[object] = field(default_factory=lambda: [
        MarketProfileEngine(),
        VolumeProfileEngine(),
        OrderFlowEngine(),
        CamarillaEngine(),
        CprEngine(),
        VwapEngine(),
        SessionContextEngine(),
    ])

    def build(self, frame: pd.DataFrame) -> pd.DataFrame:
        feature_frame = frame.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
        for engine in self.engines:
            feature_frame = engine.transform(feature_frame)
        return feature_frame.sort_values(["timestamp", "symbol", "session_date"]).reset_index(drop=True)

    def export(self, frame: pd.DataFrame, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.suffix == ".parquet":
            frame.to_parquet(destination, index=False)
        else:
            frame.to_csv(destination, index=False)


def load_sample_features() -> pd.DataFrame:
    settings = get_settings()
    raw, _warnings = CsvDataLoader(default_symbol=settings.default_symbol).load(get_paths().sample_csv)
    return FeatureStoreBuilder().build(raw)
