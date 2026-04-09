from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class TargetBase(DeclarativeBase):
    pass


class Signal(TargetBase):
    __tablename__ = "signal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class TargetData(TargetBase):
    __tablename__ = "data"

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    signal_id: Mapped[int] = mapped_column(
        ForeignKey("signal.id", ondelete="CASCADE"),
        primary_key=True,
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
