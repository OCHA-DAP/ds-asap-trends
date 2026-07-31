"""Client for the JRC ASAP per-admin-unit indicator statistics export.

ASAP publishes the dekadal (10-day) mean of each indicator for every ASAP GAUL unit
-- the same numbers its automatic warning classification is thresholded on. These are
the "raster stats" behind the warnings; the rasters themselves are not needed.

The download form on https://agricultural-production-hotspots.ec.europa.eu/download.php
posts to export/rum/export.php with variable/class/sensor ids that come from
getDataDownload.php. There is no documented REST API, so this module drives that same
endpoint directly.
"""

import logging
import time
from pathlib import Path

import pandas as pd
import requests

from src.constants import (
    ASAP_EXPORT_URL,
    ASAP_META_URL,
    GAUL_LEVEL,
    INDICATORS_BY_KEY,
    RAW_DIR,
)

logger = logging.getLogger(__name__)

# The export builds a full 25-year time series server-side; be patient and polite.
REQUEST_TIMEOUT = 300
RETRY_WAIT_SECONDS = 10
MAX_RETRIES = 3


def get_metadata() -> dict:
    """Fetch the country list and valid variable/class/sensor combinations."""
    response = requests.get(ASAP_META_URL, timeout=60)
    response.raise_for_status()
    return response.json()


def raw_path(country_id: int, indicator_key: str) -> Path:
    return RAW_DIR / f"asap_{country_id}_{indicator_key}.csv"


def download_indicator(
    country_id: int,
    indicator_key: str,
    gaul_level: int = GAUL_LEVEL,
    overwrite: bool = False,
) -> Path:
    """Download one indicator's full dekadal time series for all units in a country.

    Returns the path to the cached raw CSV.
    """
    indicator = INDICATORS_BY_KEY[indicator_key]
    out_path = raw_path(country_id, indicator_key)
    if out_path.exists() and not overwrite:
        logger.info("cached, skipping: %s", out_path.name)
        return out_path

    params = {
        "gaul_level": gaul_level,
        "country_id": country_id,
        "variable_id": indicator["variable_id"],
        "class_id": indicator["class_id"],
        "classesset_id": indicator["classesset_id"],
        "sensor_id": indicator["sensor_id"],
    }

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "downloading %s (attempt %d/%d)", indicator_key, attempt, MAX_RETRIES
            )
            response = requests.get(
                ASAP_EXPORT_URL, params=params, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            if not response.text.lstrip().startswith("country_id,"):
                raise ValueError(
                    f"unexpected response for {indicator_key}: {response.text[:200]!r}"
                )
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(response.text)
            logger.info("wrote %s (%.1f KB)", out_path.name, len(response.text) / 1024)
            return out_path
        except (requests.RequestException, ValueError) as err:
            last_error = err
            logger.warning("failed: %s", err)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT_SECONDS * attempt)

    raise RuntimeError(
        f"could not download {indicator_key} for country {country_id}"
    ) from last_error


def load_indicator(country_id: int, indicator_key: str) -> pd.DataFrame:
    """Load a cached raw CSV into a tidy frame with a parsed dekad date."""
    df = pd.read_csv(raw_path(country_id, indicator_key), dtype={"date": str})
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    df["indicator"] = indicator_key
    # ASAP uses -9999-style fills for units with no valid pixels in a dekad; the
    # export leaves those blank, but guard against sentinels leaking through.
    df.loc[df["value"] <= -999, "value"] = pd.NA
    return df.rename(columns={"region_id": "asap1_id", "region_name": "adm1_name"})[
        [
            "country_id",
            "country_name",
            "asap1_id",
            "adm1_name",
            "indicator",
            "date",
            "value",
        ]
    ]
