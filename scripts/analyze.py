"""Compute ASAP indicator trends and write the JSON the GitHub Pages site reads."""

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd  # noqa: E402

from src.asap import load_indicator, raw_path  # noqa: E402
from src.constants import (  # noqa: E402
    COMMON_START_YEAR,
    COUNTRIES,
    DEFAULT_COUNTRY,
    INDICATORS,
    PROCESSED_DIR,
    SITE_DATA_DIR,
    SITE_DEKADAL_DIR,
    WARNING_Z_THRESHOLD,
)
from src.trends import (  # noqa: E402
    NATIONAL_LABEL,
    compute_trends,
    dekad_trends,
    dekadal_frame,
    derive_zscore,
    seasonal_aggregate,
    warning_frequency_shift,
)

logger = logging.getLogger(__name__)


def load_all(country_id: int) -> pd.DataFrame:
    frames = []
    for indicator in INDICATORS:
        path = raw_path(country_id, indicator["key"])
        if not path.exists():
            logger.warning("missing raw file, skipping: %s", path.name)
            continue
        frames.append(load_indicator(country_id, indicator["key"]))
    if not frames:
        raise FileNotFoundError(
            "no raw ASAP files found -- run scripts/download.py first"
        )
    return pd.concat(frames, ignore_index=True)


def national_annual(annual: pd.DataFrame) -> pd.DataFrame:
    """National rows (unweighted mean across units) for the site's charts.

    Kept out of the frame fed to `compute_trends`, which derives its own national row --
    including these there would double-count them as an extra "unit".
    """
    return (
        annual.groupby(["indicator", "year"])[
            ["mean", "min", "max", "z_mean", "z_min", "frac_below"]
        ]
        .mean()
        .reset_index()
        .assign(asap1_id=0, adm1_name=NATIONAL_LABEL)
    )


def write_dekadal_files(dekadal: pd.DataFrame, dk_trends: pd.DataFrame) -> int:
    """One JSON per indicator: the within-season series plus its per-dekad trends.

    Stored as parallel arrays rather than a list of objects -- the field names would
    otherwise repeat ~11k times per indicator. Returns total bytes written.
    """
    SITE_DEKADAL_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for indicator, group in dekadal.groupby("indicator"):
        group = group.sort_values(["asap1_id", "year", "dekad"])
        latest = group[group["year"] == group["year"].max()]
        payload = {
            "indicator": indicator,
            "unit_names": {
                str(int(r.asap1_id)): r.adm1_name
                for r in group[["asap1_id", "adm1_name"]].drop_duplicates().itertuples()
            },
            # The most recent dekad with data, so the site can default to "now".
            "latest": {
                "year": int(group["year"].max()),
                "dekad": int(latest["dekad"].max()),
            },
            "cols": {
                "unit": [int(v) for v in group["asap1_id"]],
                "year": [int(v) for v in group["year"]],
                "dekad": [int(v) for v in group["dekad"]],
                "z": [None if pd.isna(v) else round(float(v), 2) for v in group["z"]],
                "v": [
                    None if pd.isna(v) else round(float(v), 2) for v in group["value"]
                ],
            },
            "trends": round_floats(
                dk_trends[dk_trends["indicator"] == indicator]
                .drop(columns=["indicator"])
                .to_dict("records")
            ),
        }
        out = SITE_DEKADAL_DIR / f"{indicator}.json"
        out.write_text(json.dumps(payload, separators=(",", ":")))
        total += out.stat().st_size
    return total


def round_floats(obj, places: int = 4):
    """Shrink the JSON payload without losing anything the site displays.

    Small magnitudes keep significant digits rather than decimal places, so a p-value
    like 9.4e-07 survives instead of rounding to 0.0.
    """
    if isinstance(obj, float):
        if pd.isna(obj):
            return None
        if obj != 0 and abs(obj) < 10**-places:
            return float(f"{obj:.3g}")
        return round(obj, places)
    if isinstance(obj, dict):
        return {k: round_floats(v, places) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_floats(v, places) for v in obj]
    return obj


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--country", default=DEFAULT_COUNTRY, choices=sorted(COUNTRIES))
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    country_id = COUNTRIES[args.country]

    raw = load_all(country_id)
    logger.info(
        "loaded %d rows, %d indicators, %d units, %s to %s",
        len(raw),
        raw["indicator"].nunique(),
        raw["asap1_id"].nunique(),
        raw["date"].min().date(),
        raw["date"].max().date(),
    )

    # Derive z-scores once; both the annual and dekadal views reuse them.
    with_z = derive_zscore(raw)
    annual = seasonal_aggregate(with_z)
    dekadal = dekadal_frame(with_z)
    # Trends over the common window are the headline (comparable across indicators);
    # full-record trends are kept alongside since the meteo series start in 1989.
    common = annual[annual["year"] >= COMMON_START_YEAR]
    trends = pd.concat(
        [
            compute_trends(common, stat=stat, period=f"{COMMON_START_YEAR}+")
            for stat in ("z_mean", "z_min", "mean")
        ]
        + [
            compute_trends(annual, stat=stat, period="full")
            for stat in ("z_mean", "mean")
        ],
        ignore_index=True,
    )
    warn_shift = warning_frequency_shift(common)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    annual.to_csv(PROCESSED_DIR / f"annual_{args.country}.csv", index=False)
    trends.to_csv(PROCESSED_DIR / f"trends_{args.country}.csv", index=False)
    warn_shift.to_csv(
        PROCESSED_DIR / f"warning_frequency_{args.country}.csv", index=False
    )

    # Site payload: one file, small enough to load in a single fetch.
    payload = {
        "meta": {
            "country": args.country,
            "country_name": raw["country_name"].iloc[0],
            "generated": datetime.now(UTC).strftime("%Y-%m-%d"),
            "date_min": str(raw["date"].min().date()),
            "date_max": str(raw["date"].max().date()),
            "warning_threshold": WARNING_Z_THRESHOLD,
            "common_start_year": COMMON_START_YEAR,
            "current_year": int(dekadal["year"].max()),
            "indicators": [
                {
                    **{
                        k: ind[k]
                        for k in (
                            "key",
                            "label",
                            "short",
                            "units",
                            "warning_driver",
                            "published_zscore",
                        )
                    },
                    "caveat": ind.get("caveat"),
                }
                for ind in INDICATORS
                if ind["key"] in set(raw["indicator"])
            ],
            "units": (
                annual[["asap1_id", "adm1_name"]]
                .drop_duplicates()
                .sort_values("adm1_name")
                .to_dict("records")
            ),
        },
        "annual": pd.concat(
            [annual, national_annual(annual)], ignore_index=True
        ).to_dict("records"),
        # Only the common-window rows are charted; full-record trends stay in the CSVs.
        "trends": trends[trends["period"] == f"{COMMON_START_YEAR}+"].to_dict(
            "records"
        ),
        "warning_frequency": warn_shift.to_dict("records"),
    }

    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = SITE_DATA_DIR / "asap_trends.json"
    out.write_text(json.dumps(round_floats(payload), separators=(",", ":")))
    logger.info("wrote %s (%.0f KB)", out, out.stat().st_size / 1024)

    dk_trends = dekad_trends(dekadal, COMMON_START_YEAR)
    dekadal_bytes = write_dekadal_files(dekadal, dk_trends)
    logger.info(
        "wrote %d dekadal files to %s (%.0f KB total, loaded one at a time)",
        dekadal["indicator"].nunique(),
        SITE_DEKADAL_DIR,
        dekadal_bytes / 1024,
    )

    # Console summary of the headline result: national z-score trend per indicator.
    national = trends[
        (trends["adm1_name"] == NATIONAL_LABEL)
        & (trends["stat"] == "z_mean")
        & (trends["period"] == f"{COMMON_START_YEAR}+")
    ].sort_values("slope_per_decade", ascending=False)
    logger.info(
        "national z-score trends, %s onward (z per decade):\n%s",
        COMMON_START_YEAR,
        national[
            ["indicator", "slope_per_decade", "p_value", "early_mean", "late_mean"]
        ].to_string(index=False),
    )
    warn_national = warn_shift[warn_shift["adm1_name"] == NATIONAL_LABEL].sort_values(
        "change_frac_below"
    )
    logger.info(
        "share of in-season dekads below the -1 threshold, early vs late:\n%s",
        warn_national[
            ["indicator", "early_frac_below", "late_frac_below", "change_frac_below"]
        ].to_string(index=False),
    )


if __name__ == "__main__":
    main()
