"""Realistic mock data for DEMO_MODE."""
from __future__ import annotations

from datetime import datetime, timezone

from premarket.models import (
    BriefContext,
    BriefSections,
    ExpectedOpen,
    FIIDIIData,
    IndexQuote,
    NewsItem,
    StockFocus,
)


def mock_context(target_date: str) -> BriefContext:
    now = datetime.now(tz=timezone.utc)
    return BriefContext(
        generated_at=now,
        target_date=target_date,
        global_indices=[
            IndexQuote(symbol="^GSPC", name="S&P 500", last=5832.40, change_abs=-18.30, change_pct=-0.31),
            IndexQuote(symbol="^DJI", name="Dow Jones", last=42514.20, change_abs=-92.60, change_pct=-0.22),
            IndexQuote(symbol="^IXIC", name="Nasdaq", last=18540.10, change_abs=-130.40, change_pct=-0.70),
            IndexQuote(symbol="^FTSE", name="FTSE 100", last=8225.50, change_abs=12.30, change_pct=0.15),
            IndexQuote(symbol="^GDAXI", name="DAX", last=19320.80, change_abs=-44.20, change_pct=-0.23),
        ],
        asian_indices=[
            IndexQuote(symbol="^N225", name="Nikkei 225", last=39120.55, change_abs=-218.40, change_pct=-0.56),
            IndexQuote(symbol="^HSI", name="Hang Seng", last=20480.30, change_abs=42.80, change_pct=0.21),
            IndexQuote(symbol="^KS11", name="KOSPI", last=2598.40, change_abs=-7.90, change_pct=-0.30),
            IndexQuote(symbol="000001.SS", name="Shanghai Composite", last=3284.20, change_abs=8.30, change_pct=0.25),
        ],
        india_indices=[
            IndexQuote(symbol="^NSEI", name="Nifty 50", last=24148.30, change_abs=81.20, change_pct=0.34),
            IndexQuote(symbol="^NSEBANK", name="Bank Nifty", last=53420.80, change_abs=272.50, change_pct=0.51),
            IndexQuote(symbol="^INDIAVIX", name="India VIX", last=14.62, change_abs=-0.32, change_pct=-2.14),
        ],
        commodities=[
            IndexQuote(symbol="CL=F", name="Crude Oil (WTI)", last=78.20, change_abs=0.85, change_pct=1.10),
            IndexQuote(symbol="BZ=F", name="Brent Crude", last=82.40, change_abs=0.92, change_pct=1.13),
            IndexQuote(symbol="GC=F", name="Gold", last=2734.50, change_abs=8.20, change_pct=0.30),
            IndexQuote(symbol="SI=F", name="Silver", last=32.45, change_abs=0.18, change_pct=0.56),
        ],
        currencies=[
            IndexQuote(symbol="INR=X", name="USD/INR", last=84.32, change_abs=0.06, change_pct=0.07),
            IndexQuote(symbol="DX-Y.NYB", name="Dollar Index (DXY)", last=104.20, change_abs=0.18, change_pct=0.17),
            IndexQuote(symbol="EURINR=X", name="EUR/INR", last=91.85, change_abs=-0.12, change_pct=-0.13),
        ],
        gift_nifty=IndexQuote(symbol="GIFTNIFTY=F", name="GIFT Nifty", last=24098.50, change_abs=-49.80, change_pct=-0.21),
        fii_dii=FIIDIIData(
            date=target_date,
            fii_buy=12450.30,
            fii_sell=13825.10,
            fii_net=-1374.80,
            dii_buy=11280.40,
            dii_sell=9955.85,
            dii_net=1324.55,
        ),
        news=[
            NewsItem(
                headline="HDFC Bank Q4 results today; loan growth, margins in focus",
                source="Moneycontrol",
                url="https://www.moneycontrol.com/news/business/markets/sample",
                summary="Street looking for steady NIM and deposit growth commentary.",
            ),
            NewsItem(
                headline="Fed minutes signal slower pace of cuts; dollar firmer",
                source="Moneycontrol",
                url="https://www.moneycontrol.com/news/business/markets/sample",
            ),
            NewsItem(
                headline="Brent holds above $82 as OPEC+ extends voluntary cuts",
                source="Moneycontrol",
            ),
            NewsItem(
                headline="FIIs net sellers for fifth straight session in cash market",
                source="Moneycontrol",
            ),
            NewsItem(
                headline="Reliance, ONGC, IOC in focus as crude breakout takes shape",
                source="Moneycontrol",
            ),
            NewsItem(
                headline="IT pack under pressure after weak US tech close",
                source="Moneycontrol",
            ),
        ],
        fetch_warnings=[],
    )


def mock_brief() -> BriefSections:
    return BriefSections(
        headline="Nifty Eyes Soft Open as Fed Minutes Turn Hawkish; HDFC Bank in Focus",
        subhead="A firmer dollar and weaker US tech close set a cautious tone; Bank Nifty leans on private-lender earnings for direction.",
        expected_open=ExpectedOpen(direction="Gap down", magnitude="30-50 points lower", bias="Weak"),
        driving_narrative=(
            "Hawkish Fed minutes lifted the dollar and pressured US tech overnight, keeping risk appetite "
            "contained. GIFT Nifty trades at a modest discount and Asian peers are mixed, pointing to a "
            "soft Nifty open. Domestic focus shifts to HDFC Bank's results and a fresh round of FII flow data."
        ),
        global_setup=(
            "US indices closed lower with the Nasdaq leading declines after the Fed minutes flagged "
            "stickier services inflation and a slower easing path. Brent firmed past 82 dollars, reinforcing "
            "the upward bias in energy names, while the dollar index ticked higher to 104.20."
        ),
        india_setup=(
            "Nifty closed 0.34 percent higher at 24148 with Bank Nifty outperforming, but India VIX cooled "
            "to 14.62 indicating muted hedging demand. GIFT Nifty's 50-point discount points to a marginally "
            "lower open and likely range-bound first hour."
        ),
        fii_dii_commentary=(
            "FIIs were net sellers of 1375 crore in cash markets while DIIs absorbed 1325 crore of supply, "
            "extending a five-session selling streak from offshore desks. The flow imbalance keeps the index "
            "dependent on domestic bid; any DII pause would amplify weakness in high-beta pockets."
        ),
        stocks_in_focus=[
            StockFocus(ticker="HDFCBANK", rationale="Q4 results today; deposit growth and NIM trajectory key for Bank Nifty direction."),
            StockFocus(ticker="RELIANCE", rationale="Brent breakout above 82 supports upstream and refining margins."),
            StockFocus(ticker="ONGC", rationale="Direct beneficiary of crude strength; watch options activity."),
            StockFocus(ticker="INFY", rationale="IT pack under overnight pressure after weak US tech close."),
            StockFocus(ticker="TCS", rationale="Sector-wide weakness expected on Nasdaq sell-off."),
        ],
        key_risks=[
            "HDFC Bank earnings miss reprices the entire private-banking complex.",
            "Crude breakout above 84 dollars pressures OMCs and rupee in tandem.",
            "Sixth straight FII selling session if DII bid weakens through the morning.",
        ],
        trading_stance=(
            "Expect a soft open and a narrow first-hour range while the market digests HDFC Bank numbers. "
            "Bank Nifty offers cleaner setups than Nifty given the binary results event; intraday traders "
            "should favour fade-the-range tactics until 10:30 IST and reassess. Energy and PSU oil names "
            "carry positive bias on crude strength but chase only on confirmed breakouts. IT remains an "
            "avoid until US tech stabilises. Keep position sizes modest given the flow imbalance and "
            "watch USDINR around 84.40 as a sentiment tell."
        ),
    )
