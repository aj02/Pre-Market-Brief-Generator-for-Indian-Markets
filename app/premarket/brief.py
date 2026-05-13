"""Orchestrator: collect context, run LLM (or mock), persist row."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from premarket import mock_data
from premarket.config import get_settings
from premarket.db import Brief, engine
from premarket.llm import LLMClient
from premarket.models import BriefContext, BriefSections
from premarket.sources import fetch_all

log = logging.getLogger(__name__)


def today_ist_str() -> str:
    """Return today's date in IST as YYYY-MM-DD."""
    settings = get_settings()
    return datetime.now(tz=settings.tz).strftime("%Y-%m-%d")


def gather_context(target_date: str) -> BriefContext:
    """Fan-out to data sources and assemble a BriefContext."""
    glob, asia, india, sectors, commod, currs, gift, flows, news, warnings = fetch_all()
    return BriefContext(
        generated_at=datetime.now(tz=timezone.utc),
        target_date=target_date,
        global_indices=glob,
        asian_indices=asia,
        india_indices=india,
        sector_indices=sectors,
        commodities=commod,
        currencies=currs,
        gift_nifty=gift,
        fii_dii=flows,
        news=news,
        fetch_warnings=warnings,
    )


def generate_and_store(target_date: Optional[str] = None) -> Brief:
    """Top-level entry point. Honours DEMO_MODE."""
    settings = get_settings()
    target_date = target_date or today_ist_str()
    log.info("generating brief target_date=%s demo=%s", target_date, settings.demo_mode)

    if settings.demo_mode:
        # Simulate press-running latency so the UI animation is visible.
        time.sleep(3)
        ctx = mock_data.mock_context(target_date)
        sections = mock_data.mock_brief()
        model_used = "demo:mock"
    else:
        ctx = gather_context(target_date)
        client = LLMClient()
        sections = client.generate_brief(ctx)
        model_used = settings.llm_model

    return _upsert_brief(target_date, ctx, sections, model_used)


def _upsert_brief(
    target_date: str,
    ctx: BriefContext,
    sections: BriefSections,
    model_used: str,
) -> Brief:
    with Session(engine) as session:
        existing = session.exec(
            select(Brief).where(Brief.target_date == target_date)
        ).first()
        sections_json = sections.model_dump_json()
        context_json = ctx.model_dump_json()
        if existing:
            existing.generated_at = datetime.now(tz=timezone.utc)
            existing.model_used = model_used
            existing.sections_json = sections_json
            existing.context_json = context_json
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing
        row = Brief(
            target_date=target_date,
            generated_at=datetime.now(tz=timezone.utc),
            model_used=model_used,
            sections_json=sections_json,
            context_json=context_json,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


def get_brief(target_date: str) -> Optional[Brief]:
    with Session(engine) as session:
        return session.exec(select(Brief).where(Brief.target_date == target_date)).first()


def list_briefs(limit: int = 50) -> list[Brief]:
    with Session(engine) as session:
        return list(
            session.exec(
                select(Brief).order_by(Brief.target_date.desc()).limit(limit)
            )
        )


def seed_demo_if_needed() -> None:
    """At startup in DEMO_MODE, ensure today's brief exists in the DB."""
    settings = get_settings()
    if not settings.demo_mode:
        return
    target = today_ist_str()
    if get_brief(target) is not None:
        return
    log.info("DEMO_MODE: seeding mock brief for %s", target)
    ctx = mock_data.mock_context(target)
    sections = mock_data.mock_brief()
    _upsert_brief(target, ctx, sections, model_used="demo:mock")
