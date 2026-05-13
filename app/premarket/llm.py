"""DeepInfra LLM client with structured-output prompting."""
from __future__ import annotations

import json
import logging
from typing import Optional

from openai import OpenAI
from pydantic import ValidationError

from premarket.config import get_settings
from premarket.models import BriefContext, BriefSections, IndexQuote

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a senior equity-derivatives analyst writing the morning pre-market brief for active intraday and F&O traders in Indian markets. Your readers are professional retail and prop-desk traders.

You output a JSON object conforming exactly to the schema provided. Do not include any text outside the JSON object.

WRITING STYLE for all prose fields
- Professional, like a sell-side morning desk note. No hype, no emojis, no exclamation marks.
- Specific over vague. "Nifty likely opens 30-50 pts lower" beats "negative open expected".
- Active voice. Short sentences. Avoid hedging filler.
- No financial advice or buy/sell calls. Frame in terms of setups, levels, and risks.

CRITICAL RULES (anti-hallucination)
- Use ONLY numbers, levels, and facts present in the provided context.
- If a data point is missing, omit references to it -- never invent figures.
- Do NOT fabricate price levels, support/resistance, or company-specific news.
- Name stocks only if they appear in the news/context provided.

FIELD-SPECIFIC GUIDANCE
- headline: 8-14 words. Title Case. Captures the dominant tension or event of the day.
- subhead: 12-20 words. Italic dek expanding the headline. Do not wrap in underscores or asterisks; the renderer styles italics.
- driving_narrative: 3-4 sentences. Synthesise the single most important macro/flow/event driver and how it connects to the open.
- global_setup: 4-6 sentences. Cite specific index moves and levels from the context (US, Asia, commodities, currencies). Interpret, don't reprint.
- india_setup: 4-6 sentences. Cite prior close levels for Nifty / Bank Nifty / VIX, the GIFT Nifty premium/discount if present, and at least two sector indices (use the NIFTY SECTOR INDICES block) to explain breadth.
- fii_dii_commentary: One paragraph (4-6 sentences). Cite specific FII and DII net numbers, frame the streak (if visible in context), and explain positioning implications.
- stocks_in_focus: 5-8 items. Each ticker grounded in the news context. Rationale must be one specific sentence (not "in focus").
- key_risks: 3-5 short risks. Each tied to a concrete trigger (level, event, or print).
- trading_stance: One paragraph (~120-180 words). The "editorial". Cover: type of day expected, preferred setups (e.g. fade-the-range, breakout, mean-reversion), levels to watch on Nifty and Bank Nifty, sectors that look constructive vs avoid, and explicit risk-management tells (e.g. USDINR or VIX thresholds).
"""


def _format_quote(q: IndexQuote) -> str:
    if q.last is None:
        return f"- {q.name}: unavailable"
    parts = [f"{q.last:,.2f}"]
    if q.change_abs is not None and q.change_pct is not None:
        parts.append(f"({q.change_abs:+.2f}, {q.change_pct:+.2f}%)")
    return f"- {q.name}: {' '.join(parts)}"


def _render_context(ctx: BriefContext) -> str:
    """Render BriefContext into a labelled-section text block."""
    sections: list[str] = []
    sections.append(f"TARGET DATE: {ctx.target_date}")
    sections.append(f"GENERATED AT (UTC): {ctx.generated_at.isoformat()}")

    if ctx.global_indices:
        sections.append("\n== GLOBAL INDICES ==")
        sections.extend(_format_quote(q) for q in ctx.global_indices)

    if ctx.asian_indices:
        sections.append("\n== ASIAN INDICES ==")
        sections.extend(_format_quote(q) for q in ctx.asian_indices)

    if ctx.india_indices:
        sections.append("\n== INDIA INDICES (PRIOR CLOSE) ==")
        sections.extend(_format_quote(q) for q in ctx.india_indices)

    if ctx.sector_indices:
        sections.append("\n== NIFTY SECTOR INDICES (PRIOR CLOSE) ==")
        sections.extend(_format_quote(q) for q in ctx.sector_indices)

    if ctx.gift_nifty:
        sections.append("\n== GIFT NIFTY ==")
        sections.append(_format_quote(ctx.gift_nifty))

    if ctx.commodities:
        sections.append("\n== COMMODITIES ==")
        sections.extend(_format_quote(q) for q in ctx.commodities)

    if ctx.currencies:
        sections.append("\n== CURRENCIES ==")
        sections.extend(_format_quote(q) for q in ctx.currencies)

    if ctx.fii_dii:
        f = ctx.fii_dii
        sections.append("\n== FII / DII CASH FLOWS (Rs crore) ==")
        sections.append(f"Date: {f.date}")
        sections.append(f"FII: buy={f.fii_buy} sell={f.fii_sell} net={f.fii_net}")
        sections.append(f"DII: buy={f.dii_buy} sell={f.dii_sell} net={f.dii_net}")

    if ctx.news:
        sections.append("\n== OVERNIGHT NEWS ==")
        for n in ctx.news:
            line = f"- [{n.source}] {n.headline}"
            if n.summary:
                line += f" -- {n.summary}"
            sections.append(line)

    if ctx.fetch_warnings:
        sections.append("\n== FETCH WARNINGS ==")
        for w in ctx.fetch_warnings:
            sections.append(f"- {w}")

    return "\n".join(sections)


def _schema_block() -> str:
    return json.dumps(BriefSections.model_json_schema(), indent=2)


def _build_user_prompt(ctx: BriefContext, validation_error: Optional[str] = None) -> str:
    parts: list[str] = [_render_context(ctx)]
    parts.append("\n== OUTPUT SCHEMA (JSON) ==")
    parts.append(_schema_block())
    if validation_error:
        parts.append(
            "\nYour previous response failed validation: "
            f"{validation_error}. Return a corrected JSON object."
        )
    parts.append("\nReturn a single JSON object conforming to this schema.")
    return "\n".join(parts)


class LLMClient:
    """Thin wrapper around the OpenAI SDK pointed at DeepInfra."""

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.llm_model
        self._client = OpenAI(
            api_key=settings.deepinfra_api_key or "missing",
            base_url=settings.deepinfra_base_url,
        )

    def generate_brief(self, ctx: BriefContext) -> BriefSections:
        """Call the LLM and return a validated BriefSections.

        Retries once with the validation error appended on first parse failure.
        Raises RuntimeError if both attempts fail.
        """
        attempt = 0
        last_error: Optional[str] = None
        while attempt < 2:
            user_prompt = _build_user_prompt(ctx, validation_error=last_error)
            log.info(
                "calling LLM model=%s attempt=%d prompt_chars=%d",
                self.model, attempt + 1, len(user_prompt),
            )
            try:
                completion = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.4,
                )
            except Exception as exc:  # noqa: BLE001 -- network errors must surface clearly
                log.error("LLM request failed err=%s", exc)
                raise RuntimeError(f"LLM request failed: {exc}") from exc

            content = completion.choices[0].message.content or ""
            try:
                return BriefSections.model_validate_json(content)
            except ValidationError as ve:
                last_error = str(ve)
                log.warning("LLM output failed validation attempt=%d err=%s", attempt + 1, ve)
                attempt += 1

        raise RuntimeError(f"LLM output failed validation after retry: {last_error}")
