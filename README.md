# ds-asap-trends

Trends in the raw indicators behind the [JRC ASAP](https://agricultural-production-hotspots.ec.europa.eu)
agricultural-drought warnings.

**The question.** ASAP issues an automatic warning when a z-score indicator falls below
**−1** over at least 25% of a unit's active area. Those z-scores are normalized against
the **full historical record**. If an indicator has a real long-term trend, its z-score
drifts along with it — so a year that would have breached −1 in 2005 may sit comfortably
above −1 today, on identical physical conditions. The threshold quietly gets harder to
reach, and warnings become less likely over time. This repo measures that drift.

Starting scope: **South Sudan**, ASAP GAUL level 1 (the 10 former states). The export
endpoint is per-country, so adding a country is one entry in `COUNTRIES`.

📊 **[Results site](https://ocha-dap.github.io/ds-asap-trends/)**

## Where the data comes from

ASAP publishes, for every ASAP GAUL unit, the **dekadal (10-day) mean of each indicator** —
the very numbers its warning classification is thresholded on. No rasters needed.

The [download page](https://agricultural-production-hotspots.ec.europa.eu/download.php)
exposes this as a form ("Indicator Statistics") with no documented REST API. `src/asap.py`
drives the same endpoint directly:

```
GET /export/rum/export.php
    ?gaul_level=1&country_id=88&variable_id=240&class_id=1&classesset_id=1&sensor_id=3
```

Valid id combinations come from `/getDataDownload.php` (also the `asap0_id` country
lookup — note it is **not** an ISO code; South Sudan is 88). The response is a tidy CSV,
one row per unit × dekad, from **2001-05** to the current dekad. Open EC/JRC data,
no auth, attribution required.

`classesset_id` selects the aggregation mask: `1` = "during growing cycle" (in-season
pixels only), `2` = the whole landcover mask year-round. The warning classification uses
the growing-cycle variants, so those are what we track.

### Indicators

The three the warnings are actually thresholded on:

| Indicator | `variable_id` | What it is |
|---|---|---|
| zFPARc | 240 | z-score of season-cumulative FPAR — biomass shortfall |
| zWSI | 160 crop / 170 rangeland | z-score of the Water Satisfaction Index — water balance |
| SPI-3 | 40 | 3-month Standardized Precipitation Index — rainfall deficit |

Plus context indicators (FPAR, zFPAR, rainfall, temperature, soil moisture) — the
un-normalized physical variables that explain *why* a z-score drifts.

## Method

Dekadal series are seasonal and heavily autocorrelated, so we aggregate to one value per
unit-year first (`src/trends.py`), keeping the seasonal `mean`, the seasonal `min` (what a
warning actually reacts to), and `frac_below` (share of in-season dekads under −1). Then
per unit × indicator:

- **Theil-Sen** slope, reported per decade — robust to individual drought years.
- **Mann-Kendall** significance, via Kendall's tau against time.
- **Epoch shift** — first 5 years vs last 5 years, model-free.
- **Warning-frequency shift** — `frac_below` early vs late. The operational payoff.

Year-to-year persistence is not corrected for, so p-values are mildly optimistic; read
p < 0.05 as "worth looking at", not as a formal field-significant result.

### The within-season view

The trend answers "has the threshold drifted". A second question — **"how is the current
season actually tracking"** — needs the dekad-level series, so `dekadal_frame` keeps one row
per unit × year × dekad and `dekad_trends` fits a separate trend for each dekad of the
season. The site uses this to compare the current year against every prior year *at the same
point in the season*, three ways:

- **Season progression** — this year against the prior-year 10th–90th percentile envelope
  and median, dekad by dekad.
- **A dekad selector** — pins the year-over-year chart to a single dekad, which is the
  like-for-like comparison. A seasonal mean is *not* comparable mid-season, since the current
  year's is computed over a partial season; the site draws that year's marker hollow to say so.
- **All admin units at one dekad** — each unit's current value against its own history, worst
  first, so it is obvious which units sit near warning level right now.

These use each indicator's **full** record (more history, better percentiles), whereas the
trend figures use the common 2001+ window for cross-indicator comparability. The site states
which is which.

Views are linkable: `?i=<indicator>&u=<admin unit>&d=<dekad|season>`.

## Usage

```bash
uv sync
uv run python scripts/download.py --country SSD   # cached in data/raw/
uv run python scripts/analyze.py  --country SSD   # -> data/processed/ + docs/data/
```

The site is plain HTML in `docs/`, reading `docs/data/asap_trends.json` (~890 KB, the annual
and trend layer) plus `docs/data/dekadal/<indicator>.json` (~300–400 KB each, the within-season
layer, fetched only for the indicator being viewed). `.github/workflows/update.yml` re-runs both
scripts monthly and on push, then deploys Pages.

## Caveats

- **Rangeland/cropland masks and the season definitions are stationary** in ASAP. A trend
  in a unit's indicator is a trend *within a fixed mask and fixed season window*, which is
  what the warning sees, but it is not the same as a trend in actual agricultural output.
- **Trend ≠ climate signal.** zFPARc trends in particular mix climate, land-use change,
  and sensor/algorithm history (the FPAR record splices MODIS and VIIRS). A rising FPAR
  trend may be cropland expansion or intensification, not a wetter climate. The
  warning-likelihood consequence is the same either way — which is the point of the repo —
  but do not read the slope as a rainfall statement unless SPI-3 agrees.
- **Level-4 warnings** should be ignored after a unit's "reference dekad"; see the KB
  page below. This repo analyses indicators, not issued warnings, so it does not apply
  that filter.

## See also

- Team KB: `infrastructure/datasets/jrc-asap.md` — warning levels, season gating,
  thresholds, the reference-dekad caveat.
- `asap_warning_classification_v_8_0.pdf` on the ASAP site — the primary spec.
