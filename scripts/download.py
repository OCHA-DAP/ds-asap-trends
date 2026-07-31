"""Download all tracked ASAP indicators for the configured countries."""

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.asap import download_indicator  # noqa: E402
from src.constants import COUNTRIES, DEFAULT_COUNTRY, INDICATORS  # noqa: E402

PAUSE_BETWEEN_REQUESTS = 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--country",
        default=DEFAULT_COUNTRY,
        choices=sorted(COUNTRIES),
        help="ISO3 of the country to download",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="re-download indicators already cached in data/raw",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    country_id = COUNTRIES[args.country]

    for i, indicator in enumerate(INDICATORS):
        download_indicator(country_id, indicator["key"], overwrite=args.overwrite)
        if i < len(INDICATORS) - 1:
            time.sleep(PAUSE_BETWEEN_REQUESTS)

    logging.info("done: %d indicators for %s", len(INDICATORS), args.country)


if __name__ == "__main__":
    main()
