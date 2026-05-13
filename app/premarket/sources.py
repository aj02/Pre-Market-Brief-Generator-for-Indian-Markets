"""External data fetchers. Every function returns gracefully on failure."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import requests
import yfinance as yf
from bs4 import BeautifulSoup

from premarket.cache import cached
from premarket.models import FIIDIIData, IndexQuote, NewsItem

log = logging.getLogger(__name__)

GLOBAL_INDICES: dict[str, str] = {
    "^GSPC": "S&P 500",
    "^DJI": "Dow Jones",
    "^IXIC": "Nasdaq",
    "^FTSE": "FTSE 100",
    "^GDAXI": "DAX",
}

ASIAN_INDICES: dict[str, str] = {
    "^N225": "Nikkei 225",
    "^HSI": "Hang Seng",
    "^KS11": "KOSPI",
    "000001.SS": "Shanghai Composite",
}

INDIA_INDICES: dict[str, str] = {
    "^NSEI": "Nifty 50",
    "^NSEBANK": "Bank Nifty",
    "^INDIAVIX": "India VIX",
}

SECTOR_INDICES: dict[str, str] = {
    "^CNXIT": "Nifty IT",
    "^CNXAUTO": "Nifty Auto",
    "^CNXPHARMA": "Nifty Pharma",
    "^CNXMETAL": "Nifty Metal",
    "^CNXFMCG": "Nifty FMCG",
    "^CNXENERGY": "Nifty Energy",
    "^CNXREALTY": "Nifty Realty",
    "^NSMIDCP": "Nifty Midcap 100",
}

COMMODITIES: dict[str, str] = {
    "CL=F": "Crude Oil (WTI)",
    "BZ=F": "Brent Crude",
    "GC=F": "Gold",
    "SI=F": "Silver",
}

CURRENCIES: dict[str, str] = {
    "INR=X": "USD/INR",
    "DX-Y.NYB": "Dollar Index (DXY)",
    "EURINR=X": "EUR/INR",
}

GIFT_NIFTY_SYMBOL = "GIFT_NIFTY"  # synthetic; we attempt the SGX/GIFT Nifty futures contract

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _quote_from_yf(symbol: str, name: str) -> IndexQuote:
    """Fetch one quote via yfinance. Errors are captured on the model."""
    try:
        import math

        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="7d", interval="1d", auto_adjust=False)
        if hist.empty or len(hist) < 1:
            return IndexQuote(symbol=symbol, name=name, error="empty history")

        # Drop any rows where Close is NaN -- intermittent on holidays / illiquid sessions.
        hist = hist.dropna(subset=["Close"])
        if hist.empty:
            return IndexQuote(symbol=symbol, name=name, error="all closes NaN")

        last_row = hist.iloc[-1]
        last_close = float(last_row["Close"])
        if math.isnan(last_close):
            return IndexQuote(symbol=symbol, name=name, error="NaN close")
        prev_close = float(hist.iloc[-2]["Close"]) if len(hist) >= 2 else last_close
        change_abs = last_close - prev_close
        change_pct = (change_abs / prev_close * 100.0) if prev_close else 0.0
        ts = last_row.name.to_pydatetime() if hasattr(last_row.name, "to_pydatetime") else None

        return IndexQuote(
            symbol=symbol,
            name=name,
            last=round(last_close, 2),
            change_abs=round(change_abs, 2),
            change_pct=round(change_pct, 2),
            timestamp=ts,
        )
    except Exception as exc:  # noqa: BLE001 -- network/yfinance can raise broadly; we degrade
        log.warning("yfinance fetch failed symbol=%s err=%s", symbol, exc)
        return IndexQuote(symbol=symbol, name=name, error=str(exc))


def _fetch_group(symbols: dict[str, str]) -> list[IndexQuote]:
    return [_quote_from_yf(sym, name) for sym, name in symbols.items()]


@cached(ttl=300)
def fetch_global_indices() -> list[IndexQuote]:
    """US + European indices, cached 5 minutes."""
    return _fetch_group(GLOBAL_INDICES)


@cached(ttl=300)
def fetch_asian_indices() -> list[IndexQuote]:
    return _fetch_group(ASIAN_INDICES)


@cached(ttl=300)
def fetch_india_indices() -> list[IndexQuote]:
    return _fetch_group(INDIA_INDICES)


@cached(ttl=300)
def fetch_sector_indices() -> list[IndexQuote]:
    return _fetch_group(SECTOR_INDICES)


@cached(ttl=300)
def fetch_commodities() -> list[IndexQuote]:
    return _fetch_group(COMMODITIES)


@cached(ttl=300)
def fetch_currencies() -> list[IndexQuote]:
    return _fetch_group(CURRENCIES)


@cached(ttl=300)
def fetch_gift_nifty() -> Optional[IndexQuote]:
    """Try the SGX/GIFT Nifty front-month future. Returns None on failure."""
    # yfinance does not always carry GIFT Nifty cleanly; we attempt and fall back.
    candidates = ("GIFTNIFTY=F", "NIFTYUSD=X")
    for sym in candidates:
        q = _quote_from_yf(sym, "GIFT Nifty")
        if q.last is not None:
            return q
    return None


@cached(ttl=1800)
def fetch_fii_dii() -> Optional[FIIDIIData]:
    """NSE FII/DII cash-segment flows. Requires session-cookie warm-up."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": _USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
        }
    )
    try:
        session.get("https://www.nseindia.com", timeout=10)
        resp = session.get(
            "https://www.nseindia.com/api/fiidiiTradeReact", timeout=10
        )
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            return None
        fii = next((r for r in rows if r.get("category", "").upper().startswith("FII")), {})
        dii = next((r for r in rows if r.get("category", "").upper().startswith("DII")), {})
        date_str = fii.get("date") or dii.get("date") or ""
        return FIIDIIData(
            date=str(date_str),
            fii_buy=_safe_float(fii.get("buyValue")),
            fii_sell=_safe_float(fii.get("sellValue")),
            fii_net=_safe_float(fii.get("netValue")),
            dii_buy=_safe_float(dii.get("buyValue")),
            dii_sell=_safe_float(dii.get("sellValue")),
            dii_net=_safe_float(dii.get("netValue")),
        )
    except Exception as exc:  # noqa: BLE001 -- NSE often rate-limits or rotates schema
        log.warning("FII/DII fetch failed err=%s", exc)
        return None


def _safe_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


@cached(ttl=900)
def fetch_market_news(limit: int = 30) -> list[NewsItem]:
    """Moneycontrol markets news headlines."""
    url = "https://www.moneycontrol.com/news/business/markets/"
    try:
        resp = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        items: list[NewsItem] = []
        for li in soup.select("li.clearfix")[:limit]:
            anchor = li.find("a")
            if not anchor or not anchor.get("href"):
                continue
            headline = (anchor.get("title") or anchor.get_text(strip=True) or "").strip()
            if not headline:
                continue
            summary_el = li.find("p")
            summary = summary_el.get_text(strip=True) if summary_el else None
            items.append(
                NewsItem(
                    headline=headline,
                    summary=summary,
                    source="Moneycontrol",
                    url=anchor.get("href"),
                )
            )
        return items
    except Exception as exc:  # noqa: BLE001 -- scraping can fail many ways; degrade quietly
        log.warning("news fetch failed err=%s", exc)
        return []


def fetch_all() -> tuple[
    list[IndexQuote],
    list[IndexQuote],
    list[IndexQuote],
    list[IndexQuote],
    list[IndexQuote],
    list[IndexQuote],
    Optional[IndexQuote],
    Optional[FIIDIIData],
    list[NewsItem],
    list[str],
]:
    """Fan-out fetch of every source. Returns tuple plus a warnings list."""
    warnings: list[str] = []

    glob = fetch_global_indices()
    asia = fetch_asian_indices()
    india = fetch_india_indices()
    sectors = fetch_sector_indices()
    commod = fetch_commodities()
    currs = fetch_currencies()
    gift = fetch_gift_nifty()
    flows = fetch_fii_dii()
    news = fetch_market_news()

    for bucket_name, bucket in (
        ("global", glob),
        ("asia", asia),
        ("india", india),
        ("sectors", sectors),
        ("commodities", commod),
        ("currencies", currs),
    ):
        for q in bucket:
            if q.error:
                warnings.append(f"{bucket_name}:{q.symbol}: {q.error}")
    if gift is None:
        warnings.append("gift_nifty: unavailable")
    if flows is None:
        warnings.append("fii_dii: unavailable")
    if not news:
        warnings.append("news: empty")

    return glob, asia, india, sectors, commod, currs, gift, flows, news, warnings


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)
