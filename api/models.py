from datetime import datetime
from sqlalchemy import (
    Integer, String, Text, DateTime, Enum, DECIMAL,
    ForeignKey, func
)
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from api.database import Base


class KeywordTask(Base):
    __tablename__ = "keyword_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword_cn: Mapped[str] = mapped_column(String(100), nullable=False)
    keyword_ru: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("pending", "running", "done", "failed"),
        default="pending",
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        server_default=func.now(),
        server_onupdate=func.now(),
    )

    products: Mapped[list["OzonProduct"]] = relationship(
        "OzonProduct", back_populates="task", cascade="all, delete-orphan"
    )
    analysis: Mapped[list["OzonAnalysis"]] = relationship(
        "OzonAnalysis", back_populates="task", cascade="all, delete-orphan"
    )


class OzonProduct(Base):
    __tablename__ = "ozon_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("keyword_tasks.id"), nullable=False)
    keyword_ru: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    rating: Mapped[float] = mapped_column(DECIMAL(3, 2), nullable=True)
    seller: Mapped[str] = mapped_column(String(200), nullable=True)
    product_url: Mapped[str] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )

    task: Mapped["KeywordTask"] = relationship("KeywordTask", back_populates="products")


class OzonAnalysis(Base):
    __tablename__ = "ozon_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("keyword_tasks.id"), nullable=False)
    keyword_ru: Mapped[str] = mapped_column(String(200), nullable=False)
    competition_level: Mapped[str] = mapped_column(
        Enum("低", "中", "高"), nullable=True
    )
    opportunity_score: Mapped[int] = mapped_column(TINYINT, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    price_analysis: Mapped[dict] = mapped_column(JSON, nullable=True)
    gap_opportunities: Mapped[list] = mapped_column(JSON, nullable=True)
    keywords_recommend: Mapped[list] = mapped_column(JSON, nullable=True)
    action_conclusion: Mapped[str] = mapped_column(
        Enum("入场", "观望", "放弃"), nullable=True
    )
    action_reason: Mapped[str] = mapped_column(Text, nullable=True)
    next_step: Mapped[str] = mapped_column(Text, nullable=True)
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )

    task: Mapped["KeywordTask"] = relationship("KeywordTask", back_populates="analysis")
