# The Pre-Market Times

A Dockerized FastAPI web app that generates and renders a daily pre-market trading brief for Indian equity and F&O markets. It fetches global cues, India prior-session data, FII/DII flows, and overnight news; has an LLM on **DeepInfra** synthesise a structured brief; and renders the result as **a digital morning newspaper** — masthead, multi-column body, drop cap, ticker tape, the lot — rather than yet another dashboard. The visual identity is deliberate: a portfolio piece that does not look like every other Tailwind project.

---

## Screenshots

> Run `docker compose up --build` and take screenshots of `http://127.0.0.1:18450` for this section. Suggested shots:
>
> - Front page (`/`)
> - Archive index (`/archive`)
> - Empty state (clear the DB, set `DEMO_MODE=false`, hit `/`)
> - Generating state (after clicking *Set the type*)
>
> Place PNGs under `samples/` and link them from this section.

---

## Quickstart

```bash
cp .env.example .env
# Either fill DEEPINFRA_API_KEY *or* keep DEMO_MODE=true (no key needed).
docker compose up --build
# Open http://127.0.0.1:18450
```

`DEMO_MODE=true` is the default in `.env.example` so the repo runs end-to-end on a fresh clone without any external API keys. The mock brief is realistic, not placeholder lorem ipsum.

To run a real brief, set `DEMO_MODE=false` and provide `DEEPINFRA_API_KEY`. The structured JSON response is validated against `BriefSections` (see `app/premarket/models.py`); failed validation triggers one corrective retry.

---

## Ports

| Port  | Service       | Bound to    | Notes                                       |
|-------|---------------|-------------|---------------------------------------------|
| 18450 | FastAPI (web) | 127.0.0.1   | Main UI + JSON API                          |
| 18451 | _reserved_    | —           | Future split-out background worker          |
| 18452 | Postgres 16   | 127.0.0.1   | Local-only; password `premarket`            |
| 18453 | Redis 7       | 127.0.0.1   | Data-source TTL cache                       |
| 18454 | _reserved_    | —           | pgAdmin / Redis Insight if added later      |

The `18450–18459` range was chosen to avoid the usual dev defaults (3000, 5000, 8000, 8080, 5173, 4200, 5432, 6379, 27017). Every exposed port binds to `127.0.0.1` so nothing leaks to the LAN.

---

## Architecture

```
                +---------------------+
                |     Browser (HTMX)  |
                +----------+----------+
                           |
                           v
   +-----------------------+-----------------------+
   |        FastAPI + Jinja2  (port 18450)        |
   |                                              |
   |  routes/pages.py   ----  HTML front page     |
   |  routes/api.py     ----  JSON + generate flow|
   |                                              |
   |  premarket/brief.py  (orchestrator)          |
   |     |          |              |              |
   |     v          v              v              |
   |  sources.py   llm.py        db.py            |
   |     |          |              |              |
   +-----+----------+--------------+--------------+
         |          |              |
         v          v              v
   +-----------+ +------+ +-------------------+
   | yfinance, | | Deep | | Postgres 16       |
   | NSE,      | | Infra| | (briefs table)    |
   | Moneyctrl | +------+ +-------------------+
   +-----+-----+
         |
         v
   +-----------+
   | Redis 7   |  TTL cache for source responses
   +-----------+
```

---

## Data sources

| Bucket           | Source       | TTL    | Notes                                                       |
|------------------|--------------|--------|-------------------------------------------------------------|
| Global indices   | yfinance     | 5 min  | `^GSPC ^DJI ^IXIC ^FTSE ^GDAXI`                             |
| Asian indices    | yfinance     | 5 min  | `^N225 ^HSI ^KS11 000001.SS`                                |
| India indices    | yfinance     | 5 min  | `^NSEI ^NSEBANK ^INDIAVIX` (prior session)                  |
| GIFT Nifty       | yfinance     | 5 min  | Falls back across `GIFTNIFTY=F` and `NIFTYUSD=X`            |
| Commodities      | yfinance     | 5 min  | `CL=F BZ=F GC=F SI=F`                                       |
| Currencies       | yfinance     | 5 min  | `INR=X DX-Y.NYB EURINR=X`                                   |
| FII / DII flows  | NSE          | 30 min | Warm-up `nseindia.com` for cookies, then `fiidiiTradeReact` |
| Market news      | Moneycontrol | 15 min | Scrape `business/markets/` index, `li.clearfix` items       |

Every fetcher is wrapped in `@cached(ttl=...)` and degrades to an `error` field rather than raising — a missing source becomes a `fetch_warning` in the brief context.

---

## Inference notes

The brief is produced via the OpenAI Python SDK pointed at DeepInfra's OpenAI-compatible endpoint, using `response_format={"type": "json_object"}`. The model returns a JSON object validated against `BriefSections` (Pydantic v2); a validation failure triggers one corrective retry where the validation error is appended to the user message.

**Anti-hallucination posture**

- All numbers and named entities in the prose must come from the rendered context block — the system prompt explicitly forbids invention.
- Structured output enforces shape (e.g. `expected_open.direction` is a `Literal[...]`), preventing free-form drift.
- Failed validation forces a corrective second pass before bailing.
- Missing data degrades the brief instead of fabricating numbers.

**Indicative latency / cost (replace with measured values)**

| Model                                         | TTFT     | Tokens/sec | Full response | Est. cost / brief |
|-----------------------------------------------|----------|------------|---------------|-------------------|
| `meta-llama/Meta-Llama-3.1-70B-Instruct`      | ~0.6 s   | ~70–90 t/s | ~10–14 s      | ~$0.001–$0.002    |
| `meta-llama/Meta-Llama-3.1-8B-Instruct`       | ~0.25 s  | ~180 t/s   | ~3–5 s        | ~$0.0001–$0.0003  |

Numbers above are placeholders; measure on your DeepInfra deployment and update. Brief output is ~700–900 tokens. The 70B model is the default because the brief's value depends more on calibration of judgement than raw throughput, but the 8B model is a reasonable fallback when latency matters.

---

## Design notes

The UI is a **digital morning newspaper**, not a dashboard. The model: *The Pre-Market Times* — masthead, multi-column justified body, drop cap on the lede, italic dek, small-caps section labels with a hairline rule, a right-rail "Today's Numbers" sidebar, a two-up "Stocks in Play" / "Editorial" split below the body, and a scrolling ticker tape pinned to the foot.

Decisions:

- **Hand-written CSS only.** Tailwind's utility-first vocabulary actively fights newspaper typography (line-height rhythm, column rules, drop caps, small caps with letter-spacing). `app/static/css/newspaper.css` is ~430 lines.
- **No glassmorphism, no gradients, no rounded-3xl shadow-2xl, no emoji.** Dingbats (`❧`) and hairline rules instead.
- **No dark mode in v1.** The paper aesthetic only works in light. Optional later.
- **One animation: the ticker.** Newspapers don't animate. The "press running" blink-dot on the generating state is a single CSS keyframe.
- **Old Standard TT for headlines, Spectral for body, JetBrains Mono for numbers and ticker.** Old-style figures (`onum`) on by default.
- **HTMX, no SPA.** Server-rendered Jinja2 + a small HTMX-driven generate-and-poll flow. No bundler, no `node_modules`.

If a future contributor reaches for a CSS framework, they have taken a wrong turn.

---

## Roadmap

- Telegram delivery (daily push at 08:15 IST).
- Email delivery via a transactional provider.
- Parallel source fetching with `asyncio` + per-source timeouts.
- News re-ranking by relevance to current open positions.
- Corporate-actions feed (NSE bhavcopy + Moneycontrol calendar).
- Brief accuracy backtest dashboard (was the call directionally right?).
- Replace `metadata.create_all` with Alembic when the schema actually changes.

---

## Tech stack

- **Backend:** FastAPI + Uvicorn (Python 3.11)
- **Templating:** Jinja2 (server-rendered)
- **Interactivity:** HTMX (unpkg, no build step) + ~10 lines of vanilla JS
- **Styling:** Hand-written CSS with CSS variables (no Tailwind)
- **LLM:** OpenAI SDK against DeepInfra's OpenAI-compatible endpoint, JSON-mode structured output
- **Data:** `yfinance`, `requests` + `beautifulsoup4` + `lxml`
- **Validation:** Pydantic v2
- **ORM:** SQLModel (SQLAlchemy + Pydantic)
- **Database:** Postgres 16
- **Cache:** Redis 7
- **Orchestration:** docker-compose v2 (`compose.yaml`)

---

## License

MIT.
