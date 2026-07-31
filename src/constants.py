"""Project constants: ASAP endpoint parameters and the indicator set we track."""

from pathlib import Path

PROJECT_PREFIX = "ds-asap-trends"

ASAP_BASE = "https://agricultural-production-hotspots.ec.europa.eu"
# Metadata driving the download form (countries + variable/class/sensor id combos).
ASAP_META_URL = f"{ASAP_BASE}/getDataDownload.php"
# Per-admin-unit indicator statistics ("raster stats"), full dekadal time series.
ASAP_EXPORT_URL = f"{ASAP_BASE}/export/rum/export.php"

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SITE_DATA_DIR = Path(__file__).parent.parent / "docs" / "data"
# One file per indicator, fetched lazily by the site so the initial load stays small.
SITE_DEKADAL_DIR = SITE_DATA_DIR / "dekadal"

# ASAP's own country id (asap0_id), not an ISO code. From ASAP_META_URL.
COUNTRIES = {"SSD": 88}
DEFAULT_COUNTRY = "SSD"

# The GAUL level ASAP publishes stats at. Level 1 is available for every country;
# level 2 only for a subset. South Sudan: level 1 = the 10 former states.
GAUL_LEVEL = 1

# Indicator (variable_id, class_id, classesset_id, sensor_id) combinations.
#
# classesset_id 1 = "during growing cycle" (only pixels inside the growing season),
# classesset_id 2 = the whole landcover mask year-round. The warning classification
# uses the growing-cycle variants, so those are what we track.
#
# `warning_driver` marks the indicator families the ASAP automatic warnings are actually
# thresholded on (z-score < -1 over >=25% of the active area). The others are context.
#
# `published_zscore` says whether ASAP's export already returns a normalized anomaly.
# It does for zFPARc, zFPAR and SPI-3 -- but NOT for WSI: despite the download page
# tooltip describing variable 160/170 as "zWSI [Anomaly] Z-score", the export returns
# the raw Water Satisfaction Index on a 0-100% scale (`variable_name` in the CSV comes
# back as "Water Satisfaction Index (WSI)"). The z-scored WSI that the warning
# classification uses is not downloadable, so we derive our own -- see
# trends.derive_zscore.
INDICATORS = [
    {
        "key": "zfparc_crop",
        "label": "Cumulative FPAR anomaly (zFPARc), cropland",
        "short": "zFPARc crop",
        "variable_id": 240,
        "class_id": 1,
        "classesset_id": 1,
        "sensor_id": 3,
        "units": "z-score",
        "published_zscore": True,
        "warning_driver": True,
    },
    {
        "key": "zfparc_range",
        "label": "Cumulative FPAR anomaly (zFPARc), rangeland",
        "short": "zFPARc rangeland",
        "variable_id": 240,
        "class_id": 2,
        "classesset_id": 1,
        "sensor_id": 3,
        "units": "z-score",
        "published_zscore": True,
        "warning_driver": True,
    },
    {
        "key": "wsi_crop",
        "label": "Water Satisfaction Index (WSI), cropland",
        "short": "WSI crop",
        "variable_id": 160,
        "class_id": 1,
        "classesset_id": 1,
        "sensor_id": 5,
        "units": "%",
        "published_zscore": False,
        "warning_driver": True,
    },
    {
        "key": "wsi_range",
        "label": "Water Satisfaction Index (WSI), rangeland",
        "short": "WSI rangeland",
        "variable_id": 170,
        "class_id": 2,
        "classesset_id": 1,
        "sensor_id": 5,
        "units": "%",
        "published_zscore": False,
        "warning_driver": True,
    },
    {
        "key": "spi3_crop",
        "label": "3-month Standardized Precipitation Index (SPI-3), cropland",
        "short": "SPI-3 crop",
        "variable_id": 40,
        "class_id": 1,
        "classesset_id": 1,
        "sensor_id": 4,
        "units": "z-score",
        "published_zscore": True,
        "warning_driver": True,
    },
    {
        "key": "spi3_range",
        "label": "3-month Standardized Precipitation Index (SPI-3), rangeland",
        "short": "SPI-3 rangeland",
        "variable_id": 40,
        "class_id": 2,
        "classesset_id": 1,
        "sensor_id": 4,
        "units": "z-score",
        "published_zscore": True,
        "warning_driver": True,
    },
    {
        "key": "zfpar_crop",
        "label": "FPAR anomaly (zFPAR), cropland",
        "short": "zFPAR crop",
        "variable_id": 220,
        "class_id": 1,
        "classesset_id": 1,
        "sensor_id": 3,
        "units": "z-score",
        "published_zscore": True,
        "warning_driver": False,
    },
    {
        "key": "fpar_crop",
        "label": "FPAR, cropland",
        "short": "FPAR crop",
        "variable_id": 201,
        "class_id": 1,
        "classesset_id": 1,
        "sensor_id": 3,
        "units": "%",
        "published_zscore": False,
        "warning_driver": False,
        "caveat": (
            "The FPAR record is not a single stable instrument -- read a raw FPAR "
            "trend as possible sensor history or land-use change, not as climate, "
            "unless SPI-3 agrees."
        ),
    },
    {
        "key": "rain_crop",
        "label": "Rainfall (10-day total), cropland",
        "short": "Rainfall crop",
        "variable_id": 10,
        "class_id": 1,
        "classesset_id": 1,
        "sensor_id": 4,
        "units": "mm/dekad",
        "published_zscore": False,
        "warning_driver": False,
    },
    {
        "key": "temp_crop",
        "label": "Air temperature, cropland",
        "short": "Temperature crop",
        "variable_id": 140,
        "class_id": 1,
        "classesset_id": 1,
        "sensor_id": 4,
        "units": "degC",
        "published_zscore": False,
        "warning_driver": False,
    },
    {
        "key": "sm_crop",
        "label": "Soil moisture (gapfilled), cropland",
        "short": "Soil moisture crop",
        "variable_id": 190,
        "class_id": 1,
        "classesset_id": 1,
        "sensor_id": 7,
        "units": "m3/m3",
        "published_zscore": False,
        "warning_driver": False,
        "caveat": (
            "Not usable as a trend. ASAP gapfills this series only up to dekad "
            "2023-12-21 and continues with un-gapfilled soil moisture after it; the "
            "series steps down right at that cutover (mean z -0.58 after vs +0.06 "
            "before), so its apparent decline mixes a methodology change with any "
            "real signal."
        ),
    },
]

INDICATORS_BY_KEY = {ind["key"]: ind for ind in INDICATORS}

# ASAP thresholds all observational z-score indicators at -1 SD.
WARNING_Z_THRESHOLD = -1.0

# The indicator records start at different dates (meteo back to 1989, WSI 1991, MODIS
# FPAR only 2001). Trends over each indicator's own full record are not comparable
# across indicators, so the headline figures use this common window.
COMMON_START_YEAR = 2001
