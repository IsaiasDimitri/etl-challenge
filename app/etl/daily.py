from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import httpx
import pandas as pd
from sqlalchemy import and_, create_engine, delete, select
from sqlalchemy.orm import Session

from app.models.target import Signal, TargetData

EXTRACT_SIGNALS = ("wind_speed", "power")
AGGREGATIONS = ("mean", "min", "max", "std")


def _start_end_for_date(process_date: date) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(process_date, time.min, tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)
    return start_dt, end_dt


def fetch_source_data(process_date: date, source_api_url: str) -> pd.DataFrame:
    start_dt, end_dt = _start_end_for_date(process_date)

    params: list[tuple[str, str]] = [
        ("start", start_dt.isoformat()),
        ("end", end_dt.isoformat()),
    ]
    params.extend(("signals", signal) for signal in EXTRACT_SIGNALS)

    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{source_api_url.rstrip('/')}/data", params=params)
        response.raise_for_status()

    payload = response.json().get("data", [])
    frame = pd.DataFrame(payload)
    if frame.empty:
        return pd.DataFrame(columns=["timestamp", *EXTRACT_SIGNALS])

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.sort_values("timestamp")
    return frame


def aggregate_to_10min(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["timestamp", "signal_name", "value"])

    aggregated = (
        frame.set_index("timestamp")[list(EXTRACT_SIGNALS)]
        .resample("10min", label="left", closed="left")
        .agg(list(AGGREGATIONS))
    )

    aggregated.columns = [f"{signal}_{agg}" for signal, agg in aggregated.columns]
    aggregated = aggregated.reset_index()

    long_df = aggregated.melt(
        id_vars=["timestamp"],
        var_name="signal_name",
        value_name="value",
    ).dropna(subset=["value"])

    return long_df


def _ensure_signals(session: Session, signal_names: list[str]) -> dict[str, int]:
    existing_signals = session.execute(
        select(Signal).where(Signal.name.in_(signal_names))
    ).scalars().all()
    signal_map = {row.name: row.id for row in existing_signals}

    missing = [name for name in signal_names if name not in signal_map]
    if missing:
        session.add_all([Signal(name=name) for name in missing])
        session.flush()

        created = session.execute(select(Signal).where(Signal.name.in_(missing))).scalars().all()
        for row in created:
            signal_map[row.name] = row.id

    return signal_map


def load_target_data(process_date: date, target_db_url: str, frame: pd.DataFrame) -> int:
    engine = create_engine(target_db_url, future=True)
    start_dt, end_dt = _start_end_for_date(process_date)

    with Session(engine) as session:
        signal_names = sorted(frame["signal_name"].unique().tolist()) if not frame.empty else []
        signal_map = _ensure_signals(session, signal_names) if signal_names else {}
        signal_ids = [signal_map[name] for name in signal_names]

        if signal_ids:
            session.execute(
                delete(TargetData).where(
                    and_(
                        TargetData.timestamp >= start_dt,
                        TargetData.timestamp < end_dt,
                        TargetData.signal_id.in_(signal_ids),
                    )
                )
            )

        if frame.empty:
            session.commit()
            return 0

        rows = []
        for _, line in frame.iterrows():
            rows.append(
                TargetData(
                    timestamp=line["timestamp"].to_pydatetime(),
                    signal_id=signal_map[line["signal_name"]],
                    value=float(line["value"]),
                )
            )

        session.add_all(rows)
        session.commit()
        return len(rows)


def run_daily_etl(process_date: date, source_api_url: str, target_db_url: str) -> int:
    extracted = fetch_source_data(process_date, source_api_url)
    transformed = aggregate_to_10min(extracted)
    return load_target_data(process_date, target_db_url, transformed)
