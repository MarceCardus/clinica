from __future__ import annotations

import uuid
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.routes import admin, auth, bets, health, kyc, tournaments, wallet
from app.core.config import settings
from app.core.logging import configure_logging
from app.services.storage import storage_service

configure_logging()
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])


app = FastAPI(title=settings.app_name)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, limiter._rate_limit_exceeded_handler)  # type: ignore[attr-defined]
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.middleware("http")
async def add_request_id(request: Request, call_next: Callable[[Request], Response]) -> Response:
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.on_event("startup")
async def startup_event() -> None:
    storage_service.ensure_bucket()


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(kyc.router)
app.include_router(wallet.router)
app.include_router(bets.router)
app.include_router(tournaments.router)
app.include_router(admin.router)
