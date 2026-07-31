# ds-asap-trends — notes for Claude

Read `README.md` first — it carries the data source, the reverse-engineered endpoint, and
the method. This file is the delta: things easy to get wrong.

## The point of the repo

Not "is South Sudan getting drier". It is: **ASAP's z-score thresholds are fixed at −1
against a full-record climatology, so any trend in an indicator changes how often the
threshold is reachable.** A positive trend means fewer warnings for the same physical
severity. Frame results that way; the slope is a means, not the finding.

## Gotchas

- **`country_id` is ASAP's `asap0_id`, not ISO or GAUL `adm0_code`.** South Sudan = 88
  (its `adm0_code` is 74). Always resolve from `/getDataDownload.php`.
- **Only certain (variable_id, class_id, classesset_id, sensor_id) combos exist.** zWSI
  uses a *different variable_id per landcover* (160 crop, 170 rangeland) and only exists
  for `classesset_id=1`. zFPARc likewise is growing-cycle-only. Invalid combos return an
  HTML error page, not a CSV — `download_indicator` checks the `country_id,` header for
  exactly this reason.
- **Don't fit trends to the raw dekadal series.** 36 obs/year, strong seasonality, high
  autocorrelation — you get a meaningless slope and a wildly overconfident p-value. Go
  through `seasonal_aggregate` first.
- **`frac_below` is not the ASAP warning rate.** It is the share of in-season dekads where
  the *unit-mean* z-score was under −1. ASAP instead requires the threshold over ≥25% of
  the active *area*, which is a within-unit spatial criterion the aggregate stats cannot
  reproduce. It is a proxy — a good one for trend direction, not a warning count.
- **FPAR record is spliced** (MODIS then VIIRS). Treat un-normalized FPAR trends with
  suspicion; cross-check against SPI-3, which is rainfall-only.
- **Never compare a mid-season seasonal aggregate across years.** The current year's
  `z_mean`/`z_min` covers only the dekads elapsed so far, so it is not comparable to a
  complete year's. For year-over-year comparison during a season, fix the dekad
  (`yearSeriesAtDekad` on the site). The site marks the partial year with a hollow marker;
  don't remove that.
- **Two different baselines are in play, deliberately.** The within-season charts use each
  indicator's full record (better percentiles); the trend figures use `COMMON_START_YEAR`
  (cross-indicator comparability). So the season card can say "of 38 years" while the trend
  chart shows 26 points. The UI explains it — keep that explanation if you touch the copy.

## Conventions

Team defaults (uv, `src/constants.py` with `PROJECT_PREFIX`, type hints) — see the
`data-conventions` skill. Scripts prepend the repo root to `sys.path` so `src.` imports
work without installing the package.

No blob or DB dependency: raw is gitignored and re-downloadable, derived outputs are
committed so GH Pages builds standalone. Don't add a stratus dependency unless the
outputs actually need to be shared with another repo.

## The site

Vanilla HTML/SVG in `docs/`, no build step and no external requests (Pages + CSP-friendly).
Two data layers: `docs/data/asap_trends.json` loads up front; `docs/data/dekadal/<key>.json`
is fetched lazily per indicator and cached in `DK_CACHE`.

- **`DK` is null until the first dekadal fetch resolves.** `init()` paints once immediately
  for speed, then again after `switchIndicator`. Any code path reachable from that first
  paint must tolerate `DK === null` — this already caused one bug where a `?d=` URL threw
  and aborted the rest of `init()`.
- Every chart is wrapped in `guard()`, so one failure surfaces in the `#fatal` banner
  instead of silently blanking the charts after it. Keep new charts inside `guard()`.
- Chart state is mirrored to the query string (`?i=&u=&d=`), which is also the easiest way
  to test a specific view headlessly:
  `chrome --headless --dump-dom "…?i=sm_crop&u=Warab&d=19" | grep 'id="fatal" hidden'`.
