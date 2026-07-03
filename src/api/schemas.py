from __future__ import annotations

from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    csv_path: str | None = None
    symbol: str = "NIFTY_FUT"


class UploadResponse(BaseModel):
    rows: int
    warnings: list[str]
