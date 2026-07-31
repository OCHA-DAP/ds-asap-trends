"""Trend statistics for ASAP indicator time series.

Method notes
------------
The raw series are dekadal (36 per year) and strongly seasonal, and consecutive dekads
are highly autocorrelated. Fitting a trend to the raw series would both confound the
seasonal cycle and badly overstate significance. So we aggregate to one value per unit
per year first, then test the ~25-point annual series with:

- **Theil-Sen** slope (`scipy.stats.theilslopes`) -- median-of-pairwise-slopes, robust
  to the outlier years that matter most here (drought years we do not want to downweight
  into nonexistence, but also do not want driving the fit).
- **Mann-Kendall** via `scipy.stats.kendalltau` on (year, value). Kendall's tau against
  time *is* the Mann-Kendall trend test, with scipy's tie correction.

Annual aggregation removes most within-season autocorrelation but not year-to-year
persistence (e.g. multi-year ENSO-paced runs), so p-values remain mildly optimistic.
Treat p < 0.05 here as "worth looking at", not as a formal field-significant result.
"""

import numpy as np
import pandas as pd
from scipy import stats

from src.constants import INDICATORS_BY_KEY, WARNING_Z_THRESHOLD

MIN_YEARS_FOR_TREND = 10
# ASAP's own historical baseline for the z-scores is the full satellite record; we use
# the first and last 5 available years to describe how far the series has drifted.
EPOCH_YEARS = 5
# Minimum years of a given dekad-of-year needed to estimate its climatology, and a
# floor on the standard deviation so a near-constant dekad cannot explode the z-score.
MIN_YEARS_FOR_CLIMATOLOGY = 10
MIN_STD = 1e-6
NATIONAL_LABEL = "National (mean of units)"


def derive_zscore(df: pd.DataFrame) -> pd.DataFrame:
    """Add a `z` column: the value normalized per unit x dekad-of-year.

    For indicators ASAP already publishes as an anomaly (zFPARc, zFPAR, SPI-3), `z` is
    just the published value. For the raw ones (WSI, FPAR, rainfall, temperature, soil
    moisture) we standardize against the unit's own full-record climatology for that
    dekad-of-year -- the same normalization ASAP applies internally, so the resulting
    series is comparable against the -1 warning threshold.

    This is what makes WSI analysable at all: ASAP thresholds zWSI, but only raw WSI is
    downloadable.
    """
    df = df.copy()
    df["dekad"] = (
        (df["date"].dt.month - 1) * 3 + np.minimum((df["date"].dt.day - 1) // 10, 2) + 1
    )

    published = df["indicator"].map(lambda k: INDICATORS_BY_KEY[k]["published_zscore"])

    grouped = df.groupby(["indicator", "asap1_id", "dekad"])["value"]
    clim_mean = grouped.transform("mean")
    clim_std = grouped.transform("std")
    clim_n = grouped.transform("count")

    derived = (df["value"] - clim_mean) / clim_std.clip(lower=MIN_STD)
    derived = derived.where(clim_n >= MIN_YEARS_FOR_CLIMATOLOGY)

    df["z"] = np.where(published, df["value"], derived)
    df["z_is_published"] = published
    return df


def seasonal_aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse a dekadal series to one row per unit-year.

    The "during growing cycle" classes only carry values for in-season dekads, so a
    plain per-calendar-year mean is already a growing-season mean. We keep several
    summaries because they answer different questions:

    - ``mean`` / ``min``: the season in the indicator's native units.
    - ``z_mean``: has the typical season shifted, on the threshold's own scale?
    - ``z_min``: has the worst dekad of the season shifted? (what warnings react to)
    - ``frac_below``: what share of the season's dekads breached the -1 threshold?
    """
    df = derive_zscore(df).dropna(subset=["value"])
    df["year"] = df["date"].dt.year
    keys = ["indicator", "asap1_id", "adm1_name", "year"]

    out = (
        df.groupby(keys)
        .agg(
            mean=("value", "mean"),
            min=("value", "min"),
            max=("value", "max"),
            z_mean=("z", "mean"),
            z_min=("z", "min"),
            n_dekads=("value", "size"),
        )
        .reset_index()
    )

    below = (
        df.assign(below=lambda d: d["z"] < WARNING_Z_THRESHOLD)
        .groupby(keys)["below"]
        .mean()
        .reset_index(name="frac_below")
    )
    return out.merge(below, on=keys)


def _trend_one(years: np.ndarray, values: np.ndarray) -> dict:
    """Theil-Sen slope + Mann-Kendall test for a single annual series."""
    mask = np.isfinite(values)
    years, values = years[mask], values[mask]
    n = len(years)
    if n < MIN_YEARS_FOR_TREND:
        return {
            "n_years": n,
            "slope_per_decade": np.nan,
            "slope_lo": np.nan,
            "slope_hi": np.nan,
            "tau": np.nan,
            "p_value": np.nan,
            "total_change": np.nan,
            "fit_intercept": np.nan,
            "fit_year_min": np.nan,
            "fit_year_max": np.nan,
        }

    slope, intercept, lo, hi = stats.theilslopes(values, years, alpha=0.95)
    tau, p_value = stats.kendalltau(years, values)
    span = years.max() - years.min()

    return {
        "n_years": int(n),
        "slope_per_decade": float(slope * 10),
        "slope_lo": float(lo * 10),
        "slope_hi": float(hi * 10),
        "tau": float(tau),
        "p_value": float(p_value),
        # Change implied by the fitted line across the whole record -- the practically
        # meaningful number when comparing against a z-score threshold of -1.
        "total_change": float(slope * span),
        # Kept so the site can draw the fitted line: y = intercept + slope * year.
        "fit_intercept": float(intercept),
        "fit_year_min": int(years.min()),
        "fit_year_max": int(years.max()),
    }


def _epoch_shift(years: np.ndarray, values: np.ndarray) -> dict:
    """Compare the first and last EPOCH_YEARS of the record.

    Model-free companion to the fitted trend: if the early and late epochs differ by
    much, the z-score's own baseline no longer describes present-day conditions.
    """
    order = np.argsort(years)
    years, values = years[order], values[order]
    mask = np.isfinite(values)
    years, values = years[mask], values[mask]
    if len(years) < 2 * EPOCH_YEARS:
        return {"early_mean": np.nan, "late_mean": np.nan, "epoch_shift": np.nan}
    early = float(np.mean(values[:EPOCH_YEARS]))
    late = float(np.mean(values[-EPOCH_YEARS:]))
    return {
        "early_mean": early,
        "late_mean": late,
        "epoch_shift": late - early,
        "early_period": f"{int(years[0])}-{int(years[EPOCH_YEARS - 1])}",
        "late_period": f"{int(years[-EPOCH_YEARS])}-{int(years[-1])}",
    }


def compute_trends(
    annual: pd.DataFrame, stat: str = "mean", period: str = "full"
) -> pd.DataFrame:
    """Trend of `stat` per indicator x admin unit, plus a country-wide row each.

    The country-wide row is computed on the unweighted mean across units, so it reads as
    "the average unit in this country" rather than an area-weighted national figure.

    `period` is a label carried through to the output, so full-record and common-window
    trends can live in one table.
    """
    rows = []
    for (indicator, asap1_id, adm1_name), group in annual.groupby(
        ["indicator", "asap1_id", "adm1_name"]
    ):
        years = group["year"].to_numpy(dtype=float)
        values = group[stat].to_numpy(dtype=float)
        rows.append(
            {
                "indicator": indicator,
                "asap1_id": asap1_id,
                "adm1_name": adm1_name,
                "stat": stat,
                "period": period,
                **_trend_one(years, values),
                **_epoch_shift(years, values),
            }
        )

    national = annual.groupby(["indicator", "year"])[stat].mean().reset_index(name=stat)
    for indicator, group in national.groupby("indicator"):
        years = group["year"].to_numpy(dtype=float)
        values = group[stat].to_numpy(dtype=float)
        rows.append(
            {
                "indicator": indicator,
                "asap1_id": 0,
                "adm1_name": NATIONAL_LABEL,
                "stat": stat,
                "period": period,
                **_trend_one(years, values),
                **_epoch_shift(years, values),
            }
        )

    return pd.DataFrame(rows)


def warning_frequency_shift(annual: pd.DataFrame) -> pd.DataFrame:
    """How often each unit's z-score breached -1, early epoch vs late epoch.

    This is the operational payoff: the share of in-season dekads at or below the ASAP
    warning threshold. If an indicator trends up, this share falls, and warnings that
    the threshold was calibrated to catch stop being issued.
    """
    per_unit = annual[["indicator", "asap1_id", "adm1_name", "year", "frac_below"]]
    national = (
        annual.groupby(["indicator", "year"])["frac_below"]
        .mean()
        .reset_index()
        .assign(asap1_id=0, adm1_name=NATIONAL_LABEL)
    )
    combined = pd.concat([per_unit, national], ignore_index=True)

    rows = []
    for (indicator, asap1_id, adm1_name), group in combined.groupby(
        ["indicator", "asap1_id", "adm1_name"]
    ):
        group = group.sort_values("year")
        years = group["year"].to_numpy(dtype=float)
        frac = group["frac_below"].to_numpy(dtype=float)
        if len(years) < 2 * EPOCH_YEARS:
            continue
        rows.append(
            {
                "indicator": indicator,
                "asap1_id": asap1_id,
                "adm1_name": adm1_name,
                "early_frac_below": float(np.mean(frac[:EPOCH_YEARS])),
                "late_frac_below": float(np.mean(frac[-EPOCH_YEARS:])),
                "early_period": f"{int(years[0])}-{int(years[EPOCH_YEARS - 1])}",
                "late_period": f"{int(years[-EPOCH_YEARS])}-{int(years[-1])}",
                **{
                    f"trend_{k}": v
                    for k, v in _trend_one(years, frac).items()
                    if k in ("slope_per_decade", "p_value", "tau")
                },
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["change_frac_below"] = df["late_frac_below"] - df["early_frac_below"]
    return df
