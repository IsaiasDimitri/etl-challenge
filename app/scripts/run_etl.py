from __future__ import annotations

import argparse
from datetime import date

from app.config import get_settings
from app.etl.daily import run_daily_etl


def main() -> None:
    parser = argparse.ArgumentParser(description="Run daily ETL for a given date")
    parser.add_argument("--date", required=True, help="Date in YYYY-MM-DD format")
    args = parser.parse_args()

    settings = get_settings()
    process_date = date.fromisoformat(args.date)

    loaded_rows = run_daily_etl(
        process_date=process_date,
        source_api_url=settings.source_api_url,
        target_db_url=settings.target_db_url,
    )
    print(f"Loaded {loaded_rows} rows for {process_date.isoformat()}")


if __name__ == "__main__":
    main()
