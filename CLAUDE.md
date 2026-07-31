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

## Conventions

Team defaults (uv, `src/constants.py` with `PROJECT_PREFIX`, type hints) — see the
`data-conventions` skill. Scripts prepend the repo root to `sys.path` so `src.` imports
work without installing the package.

No blob or DB dependency: raw is gitignored and re-downloadable, derived outputs are
committed so GH Pages builds standalone. Don't add a stratus dependency unless the
outputs actually need to be shared with another repo.
