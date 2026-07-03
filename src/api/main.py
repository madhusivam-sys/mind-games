from __future__ import annotations

from fastapi import FastAPI

from api.routes import router as analytics_router
from api.routes_context import router as context_router
from api.routes_market_active import router as market_router
from utils.config import get_settings

app = FastAPI(title=get_settings().app_name, version="0.2.0", description="Decision-support analytics API for intraday index futures.")
app.include_router(analytics_router)
app.include_router(context_router)
app.include_router(market_router)
