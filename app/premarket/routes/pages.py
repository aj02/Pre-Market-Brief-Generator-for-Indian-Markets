"""Jinja-rendered HTML routes."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from premarket import brief as brief_svc
from premarket.config import get_settings
from premarket.models import BriefContext, BriefSections

log = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter()


def _render_brief_page(request: Request, row) -> HTMLResponse:
    sections = BriefSections.model_validate_json(row.sections_json)
    context = BriefContext.model_validate_json(row.context_json)
    settings = get_settings()
    generated_local = row.generated_at.astimezone(settings.tz)
    return templates.TemplateResponse(
        "brief.html",
        {
            "request": request,
            "sections": sections,
            "context": context,
            "target_date": row.target_date,
            "generated_at_local": generated_local,
            "model_used": row.model_used,
            "edition_label": _edition_label(row.target_date),
        },
    )


def _edition_label(date_str: str) -> dict[str, str]:
    """Format the date string into masthead components."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return {"weekday": "", "long_date": date_str, "vol": ""}
    return {
        "weekday": d.strftime("%A"),
        "long_date": d.strftime("%d %B %Y"),
        "vol": f"Vol I, No {d.timetuple().tm_yday}",
    }


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    target = brief_svc.today_ist_str()
    row = brief_svc.get_brief(target)
    if row is None:
        return templates.TemplateResponse(
            "empty.html",
            {
                "request": request,
                "target_date": target,
                "edition_label": _edition_label(target),
            },
        )
    return _render_brief_page(request, row)


@router.get("/briefs/{date}", response_class=HTMLResponse)
def brief_by_date(request: Request, date: str) -> HTMLResponse:
    row = brief_svc.get_brief(date)
    if row is None:
        return templates.TemplateResponse(
            "empty.html",
            {
                "request": request,
                "target_date": date,
                "edition_label": _edition_label(date),
                "not_found": True,
            },
            status_code=404,
        )
    return _render_brief_page(request, row)


@router.get("/archive", response_class=HTMLResponse)
def archive(request: Request) -> HTMLResponse:
    rows = brief_svc.list_briefs(limit=200)
    items = []
    for r in rows:
        try:
            s = BriefSections.model_validate_json(r.sections_json)
            headline = s.headline
        except Exception:  # noqa: BLE001 -- archive must render even on partial corruption
            headline = "(unreadable)"
        items.append(
            {
                "target_date": r.target_date,
                "headline": headline,
                "edition_label": _edition_label(r.target_date),
            }
        )
    return templates.TemplateResponse(
        "archive.html",
        {"request": request, "items": items},
    )


@router.get("/healthz", response_class=PlainTextResponse)
def healthz() -> str:
    return "ok"
