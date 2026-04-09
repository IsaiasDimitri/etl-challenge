from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_source_session, source_engine
from app.models.source import SourceBase, SourceData

app = FastAPI(title="Source Connector API", version="1.0.0")

ALLOWED_SIGNALS = {"wind_speed", "power", "ambient_temprature"}


@app.on_event("startup")
def startup_event() -> None:
    SourceBase.metadata.create_all(bind=source_engine)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/data")
def get_data(
    start: datetime,
    end: datetime,
    signals: Annotated[list[str], Query(min_length=1)],
    session: Session = Depends(get_source_session),
) -> dict[str, object]:
    if start >= end:
        raise HTTPException(status_code=400, detail="start must be before end")

    dedup_signals = list(dict.fromkeys(signals))
    invalid_signals = sorted(set(dedup_signals) - ALLOWED_SIGNALS)
    if invalid_signals:
        raise HTTPException(
            status_code=400,
            detail=f"invalid signals: {', '.join(invalid_signals)}",
        )

    selected_columns = [SourceData.timestamp] + [getattr(SourceData, name) for name in dedup_signals]

    stmt = (
        select(*selected_columns)
        .where(SourceData.timestamp >= start, SourceData.timestamp < end)
        .order_by(SourceData.timestamp)
    )
    rows = session.execute(stmt).all()

    payload = []
    for row in rows:
        row_dict = dict(row._mapping)
        payload.append(row_dict)

    return {
        "count": len(payload),
        "signals": dedup_signals,
        "data": payload,
    }
