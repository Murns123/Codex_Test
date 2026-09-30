# MEL → ELS flight price tracker

Tracks one trip, Melbourne (MEL) to East London (ELS) and back, economy, 1 adult, AUD. It runs 3 times a
day on Vercel and tells you whether to **BUY** or **HOLD**.

| | |
|---|---|
| Primary dates | out **21 Dec 2026**, back **8 Jan 2027** |
| Flex dates | out 19 / 20 / 22 Dec, back 7 / 9 / 10 Jan |
| Tracking window | until **31 Oct 2026** (hard stop); from **14 Oct** it recommends booking |
| Output | web dashboard at `/`, JSON at `/api/report`, run log at `/api/log` (no email) |
| Schedule | 07:00, 12:00 and 17:00 Melbourne time (Vercel Cron) |

Python 3.12. No database service is needed: on Vercel every run is stored as JSON in **Vercel Blob**
(Vercel's built-in file storage). Local CLI runs use SQLite.

## How it works

```
Ignav (primary) ─┐
SerpApi (opt.)  ─┼─> normalise -> classify route A–E -> value_score -> rules -> JEV 2nd opinion -> store -> dashboard
                 └─ raw JSON of every call stored per run (audit)
```

**Route tags**

- **A**: Qantas via PER to JNB, then a connection to ELS
- **B**: Qantas via SYD to JNB, then a connection to ELS
- **C**: SAA via PER
- **D**: EK, QR, EY or SQ via its hub to JNB, DUR or CPT, then ELS
- **E**: self-transfer or separate tickets
- **X**: a single ticket that fits none of the above. It is shown as X rather than forced into a category.
- If the two directions differ, the tag shows both, e.g. `A/B`.

**Scoring** (config.yaml → `scoring`)

```
value_score = price + 50 × max(0, hours_out − 22) + 50 × max(0, hours_back − 22)
```

An option is flagged **too long** if either direction is over 30h. The flag is dropped if its price is more
than AUD 500 below the cheapest option that isn't too long.

**Decision rules** (config.yaml → `decision`). These are evaluated in order, and the first match wins:

1. After 31 Oct → STOP. No API calls are made.
2. No usable single-ticket fares → HOLD, with the reason given. Nothing is estimated.
3. On or after 14 Oct → BUY the best single-ticket option. On 31 Oct the reason says it's the final day.
4. Best single-ticket **price** under AUD 3,000 → BUY.
5. Best **value_score** 5% or more below the day-1 baseline → BUY.
6. Best value_score has risen 2 times in a row → BUY.
7. Day 1 → HOLD (sets the baseline).
8. Movement under 3% → HOLD. Anything else → HOLD, with the % move stated.

**3 runs a day vs "daily" rules.** With `trend_basis: day` (the default), "yesterday", "baseline" and "risen
2 in a row" use each day's *latest* run. The spec's daily semantics still hold, and the extra runs catch
intraday drops. Set `trend_basis: run` to compare every run instead. "Day X" is the number of calendar days
with at least one run.

### JEV second opinion

Each run sends JEV (`api.typesafe.ai/v1/systemone`, the same API as the paper trader) a full statistical
picture:

- **Today's fares:** price and value-score quartiles, spread, per-route cheapest/fastest, per-date-pair best,
  flex saving, cheapest self-transfer.
- **History:** baseline, all-time low/high, mean, stdev, z-score, percentile, 7-day mean, and least-squares
  slope (all-time and 7-day, AUD/day).
- **Movement:** daily % changes, volatility, up/down days, largest rise/drop, streaks, intraday range.
- **Calendar:** days to book-by, hard stop and departure.
- **Context:** the top 10 options, the rules engine's decision, and provider health.

It answers 14 questions:

- **11 probabilities:** e.g. *likely to rise in 7 days*, *5% drop before book-by likely*, *connection risk
  high*, *flex dates worth it*, *data-quality concern*.
- **2 choices:** *action* (buy_now / buy_flex / hold) and *preferred route* (A/B/C/D).
- **1 score:** *urgency* (1–5).

All answers appear on the dashboard.

Safety model: **the rules decide; JEV can only upgrade a HOLD to a BUY**. This happens only when
P(buy_now) + P(buy_flex) ≥ `jev.upgrade_hold_threshold` (0.80), and only from day 3. JEV never downgrades
a BUY and is never asked for a price. Set the threshold to `null` to make JEV advisory only. If JEV fails,
the dashboard says so and the rules' decision stands.

### Never inventing fares

- A provider that fails, whether from retries exhausted, a bad key or a crash, is listed on the dashboard
  and in the log as **FAILED**, with the error. The run carries on with whatever the other providers
  returned.
- Rows the parser can't read with confidence are dropped and counted. This covers a missing price, a
  missing leg duration, or a price in another currency. Durations are never computed from local times in
  different time zones.
- If nothing usable comes back, the top-3 table is empty and the decision is HOLD with `no_data`.
- `--fixtures` data is labelled **FIXTURE DATA** on every output, and JEV is not called for it.

## Local setup

```bash
cd flight_tracker
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # add IGNAV_API_KEY, optionally SERPAPI_KEY and JEV_API_KEY
python tracker.py probe     # one Ignav call – check the parsed output looks right (see below)
python tracker.py run --dry-run
python tracker.py run
python tracker.py report            # latest analysis, no API calls
python tracker.py report --html out.html
pytest -q
```

**Commands**

- `run`: searches, decides, then writes to SQLite, `data/raw/<date>/`, `logs/daily_log.md` and
  `logs/tracker.log`.
- `--dry-run`: calls the APIs and prints the analysis but saves nothing.
- `--fixtures tests/fixtures/ignav_sample.json`: replays test data with no API calls (pipeline testing only).

**Check the Ignav parser before relying on it.** Ignav's docs couldn't be read from the build environment.
The adapter follows the published endpoint (`POST https://ignav.com/api/fares/round-trip`, `X-Api-Key`
header) and accepts the common field-name variants. Run `python tracker.py probe` once with your key and
compare `data/probe_ignav.json` with the parsed lines it prints. If a field is named differently, add it to
the `_first(...)` lists in `fttracker/providers/ignav.py`. If the request body needs different keys, set
`providers.ignav.extra_body` in config.yaml.

Local cron (daily at 17:00 Melbourne; needs cronie or another cron that supports `CRON_TZ`):

```cron
CRON_TZ=Australia/Melbourne
0 17 * * * cd /path/to/flight_tracker && .venv/bin/python tracker.py run >> logs/cron.log 2>&1
# 3x a day instead:
# 0 7,12,17 * * * cd /path/to/flight_tracker && .venv/bin/python tracker.py run >> logs/cron.log 2>&1
```

## Deploy to Vercel

This deploys as its **own Vercel project**, separate from the Next.js paper trader at the repo root.

1. Vercel → **Add New Project** → import this repo → set **Root Directory** to `flight_tracker`. Framework
   preset: *Other*.
2. **Storage** → create a **Blob** store (private, region Sydney) and connect it to the project. This sets
   `BLOB_READ_WRITE_TOKEN`. Layout inside the store:
   - `runs/index.json`: one summary row per run (drives trend, baseline, log).
   - `runs/<id>.json`: the full report and itineraries for that run.
   - `raw/<date>/<id>_<label>.json`: every provider and JEV response, for audit.

   If `index.json` is ever lost, it is rebuilt from the per-run files, so the baseline survives.
   `/api/selftest` checks the connection (put/list/get round trip) and shows which env vars are set.
3. **Settings → Environment Variables:**
   - `IGNAV_API_KEY`
   - `CRON_SECRET`: any long random string. Vercel sends it to the cron endpoint, and requests without it
     get a 401.
   - Optional: `SERPAPI_KEY`, `JEV_API_KEY`, `JEV_MODEL`.
4. Deploy. Trigger a first run with `vercel crons run /api/cron`, or with
   `curl -H "Authorization: Bearer $CRON_SECRET" https://<app>.vercel.app/api/cron`.

The crons in `vercel.json` are in **UTC**:

| UTC | Melbourne from 4 Oct (AEDT) | Melbourne before 4 Oct (AEST) |
|---|---|---|
| `0 20 * * *` | 07:00 | 06:00 |
| `0 1 * * *` | 12:00 | 11:00 |
| `0 6 * * *` | 17:00 | 16:00 |

They are three separate once-a-day entries, which is the pattern that fits Hobby-plan cron limits. On Hobby
each can fire any time within its hour. Check the current limits at
<https://vercel.com/docs/cron-jobs/usage-and-pricing>.

`maxDuration` is 300s. Ignav calls run 4 in parallel, so a normal run takes well under a minute.

## Cost per run

| Service | Calls per run | Per day (3 runs) | Oct 1 → 31 |
|---|---|---|---|
| Ignav | 7 (`flex_mode: cross`) or 16 (`grid`) | 21 / 48 | ~650 / ~1,490 |
| SerpApi (optional) | 3 (1 search + 2 return-leg expansions, primary dates only) | 9 | ~280 |
| JEV (optional) | 1 (~8–15k input tokens: stats + top 10 options) | 3 | ~93 |
| Vercel + Blob | 1 function run of up to ~60s; ~10–20 small JSON writes | ~50 | Hobby free tier normally covers this |

Cost per run = calls × your plan's per-call price. Check the current prices:

- Ignav: <https://ignav.com/pricing>
- SerpApi: <https://serpapi.com/pricing>. The free tier is unlikely to cover ~280 searches a month, so
  lower `return_legs_for_top_n` or disable SerpApi if needed.
- JEV: your typesafe.ai plan.

The run count per provider is also stored on every run (`api_calls` in `/api/report`), so actual usage can
be checked. To cut cost, use `flex_mode: cross` (the default), set `serpapi.enabled: false`, or remove one
of the three crons.

## Layout

```
flight_tracker/
  tracker.py              CLI: run / report / probe
  config.yaml             trip, scoring, thresholds, providers, JEV
  vercel.json             functions, rewrite / -> /api/index, 3 crons
  api/                    Vercel functions: cron, index (dashboard), report (JSON), log, selftest
  fttracker/
    providers/            pluggable: base.FareProvider, ignav, serpapi, fixture
    classify.py           route A–E
    scoring.py            value_score, too-long flag
    decision.py           BUY/HOLD rules + JEV upgrade gate
    stats.py              statistics for dashboard + JEV
    jev.py                JEV questions and client
    storage.py            SQLite (local) / JSON documents (Vercel Blob)
    blobstore.py          Vercel Blob HTTP client + local-directory store
    report.py             text + HTML dashboard
    runner.py             one run end to end
  tests/                  58 tests incl. scoring, decision rules, classification, parsers, retries
```

To add a provider, subclass `FareProvider`, return `Itinerary` objects, and add it to
`fttracker/providers/__init__.py`.
