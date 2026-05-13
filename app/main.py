"""FastAPI application factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from premarket import brief as brief_svc
from premarket.config import configure_logging, get_settings
from premarket.db import init_db
from premarket.routes import api as api_routes
from premarket.routes import pages as page_routes

log = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    log.info("starting premarket app demo_mode=%s tz=%s", settings.demo_mode, settings.timezone)
    init_db()
    try:
        brief_svc.seed_demo_if_needed()
    except Exception as exc:  # noqa: BLE001 -- seed failure must not block startup
        log.warning("demo seed failed err=%s", exc)
    yield
    log.info("shutting down premarket app")


def create_app() -> FastAPI:
    app = FastAPI(title="The Pre-Market Times", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    app.include_router(page_routes.router)
    app.include_router(api_routes.router)

    # Lightweight not-found page that keeps the paper aesthetic.
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):  # type: ignore[no-untyped-def]
        # API endpoints get JSON; page routes get the paper-themed empty.
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "not found"}, status_code=404)
        return templates.TemplateResponse(
            "empty.html",
            {
                "request": request,
                "target_date": "",
                "edition_label": {"weekday": "", "long_date": "", "vol": ""},
                "not_found": True,
            },
            status_code=404,
        )

    return app


app = create_app()
