from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.db.base import Base
from app.models.hara import HaraArea
from app.models.user import User


class HaraZoneCluster(Base):
    __tablename__ = "hara_zone_cluster"

    area_id: Mapped[int] = mapped_column(
        ForeignKey("hara_bogor.id", ondelete="CASCADE"),
        primary_key=True,
    )
    cluster_id: Mapped[int] = mapped_column(Integer, nullable=False)
    zone_key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    zone_label: Mapped[str] = mapped_column(String(64), nullable=False)
    dist_to_centroid: Mapped[float | None] = mapped_column(Float, nullable=True)
    dist_to_second: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    trained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    area: Mapped[HaraArea] = relationship(HaraArea)


class HaraZoneLabelOverride(Base):
    __tablename__ = "hara_zone_label_override"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    area_id: Mapped[int] = mapped_column(
        ForeignKey("hara_bogor.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zone_key: Mapped[str] = mapped_column(String(32), nullable=False)
    expert_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    area: Mapped[HaraArea] = relationship(HaraArea)
    expert: Mapped[User] = relationship(User)


class AnalysisReview(Base):
    __tablename__ = "analysis_review"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    area_id: Mapped[int] = mapped_column(
        ForeignKey("hara_bogor.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expert_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)  # 'validated' | 'overridden'
    zone_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    area: Mapped[HaraArea] = relationship(HaraArea)
    expert: Mapped[User] = relationship(User)


def ensure_zone_cluster_tables(db: Session) -> None:
    Base.metadata.create_all(
        bind=db.get_bind(),
        tables=[
            User.__table__,
            HaraArea.__table__,
            HaraZoneCluster.__table__,
            HaraZoneLabelOverride.__table__,
            AnalysisReview.__table__,
        ],
    )
