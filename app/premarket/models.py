"""Pydantic models for inputs to the LLM and structured brief output."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class IndexQuote(BaseModel):
    symbol: str
    name: str
    last: Optional[float] = None
    change_pct: Optional[float] = None
    change_abs: Optional[float] = None
    timestamp: Optional[datetime] = None
    error: Optional[str] = None


class NewsItem(BaseModel):
    headline: str
    summary: Optional[str] = None
    source: str
    url: Optional[str] = None


class FIIDIIData(BaseModel):
    date: str
    fii_buy: Optional[float] = None
    fii_sell: Optional[float] = None
    fii_net: Optional[float] = None
    dii_buy: Optional[float] = None
    dii_sell: Optional[float] = None
    dii_net: Optional[float] = None


class BriefContext(BaseModel):
    """Everything fed to the LLM."""

    generated_at: datetime
    target_date: str
    global_indices: list[IndexQuote] = Field(default_factory=list)
    asian_indices: list[IndexQuote] = Field(default_factory=list)
    india_indices: list[IndexQuote] = Field(default_factory=list)
    sector_indices: list[IndexQuote] = Field(default_factory=list)
    commodities: list[IndexQuote] = Field(default_factory=list)
    currencies: list[IndexQuote] = Field(default_factory=list)
    gift_nifty: Optional[IndexQuote] = None
    fii_dii: Optional[FIIDIIData] = None
    news: list[NewsItem] = Field(default_factory=list)
    fetch_warnings: list[str] = Field(default_factory=list)


class StockFocus(BaseModel):
    ticker: str
    rationale: str


class ExpectedOpen(BaseModel):
    direction: Literal["Gap up", "Gap down", "Flat"]
    magnitude: str
    bias: Literal["Strong", "Moderate", "Weak", "Mixed"]


class BriefSections(BaseModel):
    """Structured brief output by the LLM."""

    headline: str
    subhead: str
    expected_open: ExpectedOpen
    driving_narrative: str
    global_setup: str
    india_setup: str
    fii_dii_commentary: str
    stocks_in_focus: list[StockFocus]
    key_risks: list[str]
    trading_stance: str
