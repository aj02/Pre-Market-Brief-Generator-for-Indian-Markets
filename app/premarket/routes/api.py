"""JSON API + HTMX-driven generation endpoints."""
from __future__ import annotations

import logging
import threading
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from premarket import brief as brief_svc
from premarket.models import BriefSections

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# Simple in-process job state for the HTMX generate-and-poll flow.
# Single-user local app, so a module-level dict + lock is sufficient.
_JOB_LOCK = threading.Lock()
_JOB: dict[str, Any] = {"state": "idle", "progress": "", "brief_id": None, "error": None}


def _set_job(**kwargs: Any) -> None:
    with _JOB_LOCK:
        _JOB.update(kwargs)


def _get_job() -> dict[str, Any]:
    with _JOB_LOCK:
        return dict(_JOB)


def _row_to_payload(row) -> dict[str, Any]:
    sections = BriefSections.model_validate_json(row.sections_json)
    return {
        "target_date": row.target_date,
        "generated_at": row.generated_at.isoformat(),
        "model_used": row.model_used,
        "sections": sections.model_dump(),
    }


@router.get("/briefs/today")
def get_today() -> JSONResponse:
    target = brief_svc.today_ist_str()
    row = brief_svc.get_brief(target)
    if row is None:
        raise HTTPException(status_code=404, detail="no brief for today")
    return JSONResponse(_row_to_payload(row))


@router.get("/briefs/{date}")
def get_by_date(date: str) -> JSONResponse:
    row = brief_svc.get_brief(date)
    if row is None:
        raise HTTPException(status_code=404, detail="not found")
    return JSONResponse(_row_to_payload(row))


def _run_generation_job() -> None:
    """Background worker: drive generation and update _JOB state."""
    try:
        _set_job(state="running", progress="Plate 1 of 3 -- gathering data", error=None)
        # The orchestrator does everything; we just update the visible label
        # so the marquee shows progress even though stages are coarse here.
        row = brief_svc.generate_and_store()
        _set_job(state="done", progress="Plate 3 of 3 -- press complete", brief_id=row.id, error=None)
    except Exception as exc:  # noqa: BLE001 -- surface anything to the UI
        log.exception("generation job failed")
        _set_job(state="error", progress="", brief_id=None, error=str(exc))


@router.post("/briefs/generate")
def trigger_generate(background: BackgroundTasks) -> HTMLResponse:
    """Kicks off generation. Returns the HTMX-friendly running marquee fragment."""
    current = _get_job()
    if current["state"] == "running":
        marquee = _marquee_html(current.get("progress") or "Plate 1 of 3")
        return HTMLResponse(marquee)

    _set_job(state="running", progress="Plate 1 of 3 -- gathering data", brief_id=None, error=None)
    background.add_task(_run_generation_job)
    return HTMLResponse(_marquee_html("Plate 1 of 3 -- gathering data"))


@router.get("/briefs/generate/status")
def generate_status() -> JSONResponse:
    job = _get_job()
    return JSONResponse(job)


def _marquee_html(progress: str) -> str:
    """HTML fragment swapped in by HTMX after triggering generation."""
    return (
        '<div id="press-marquee" class="press-marquee" '
        'hx-get="/api/briefs/generate/status" hx-trigger="every 2s" '
        'hx-swap="outerHTML" hx-target="#press-marquee" '
        f'data-progress="{progress}">'
        f'<span class="press-dot">&#9679;</span> PRESS RUNNING &middot; {progress}'
        "</div>"
    )
