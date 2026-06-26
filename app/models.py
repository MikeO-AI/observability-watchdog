"""ORM models: ingestions, parsed log entries, detected anomalies, and alerts."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Ingestion(Base):
    __tablename__ = "ingestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(255), default="upload")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    total_lines: Mapped[int] = mapped_column(Integer, default=0)
    parsed_lines: Mapped[int] = mapped_column(Integer, default=0)
    error_lines: Mapped[int] = mapped_column(Integer, default=0)
    anomaly_count: Mapped[int] = mapped_column(Integer, default=0)

    entries: Mapped[list["LogEntry"]] = relationship(back_populates="ingestion")
    anomalies: Mapped[list["Anomaly"]] = relationship(back_populates="ingestion")


class LogEntry(Base):
    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    ingestion_id: Mapped[int] = mapped_column(ForeignKey("ingestions.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    level: Mapped[str] = mapped_column(String(16), index=True)
    service: Mapped[str | None] = mapped_column(String(128), nullable=True)
    message: Mapped[str] = mapped_column(Text)

    ingestion: Mapped["Ingestion"] = relationship(back_populates="entries")


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(primary_key=True)
    ingestion_id: Mapped[int] = mapped_column(ForeignKey("ingestions.id"), index=True)
    bucket_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    window_seconds: Mapped[int] = mapped_column(Integer)
    error_count: Mapped[int] = mapped_column(Integer)
    total_count: Mapped[int] = mapped_column(Integer)
    baseline_mean: Mapped[float] = mapped_column(Float)
    baseline_std: Mapped[float] = mapped_column(Float)
    zscore: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    analyzed: Mapped[bool] = mapped_column(Boolean, default=False)
    analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    ingestion: Mapped["Ingestion"] = relationship(back_populates="anomalies")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="anomaly")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    anomaly_id: Mapped[int] = mapped_column(ForeignKey("anomalies.id"), index=True)
    webhook_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    anomaly: Mapped["Anomaly"] = relationship(back_populates="alerts")
