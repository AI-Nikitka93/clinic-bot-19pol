from datetime import datetime, date, time as dt_time
from typing import Optional, List
from sqlalchemy import String, Integer, Date, Time, ForeignKey, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    subscriptions: Mapped[List["Subscription"]] = relationship(back_populates="user")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    base_url: Mapped[str] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(default=True)

    specialties: Mapped[List["Specialty"]] = relationship(back_populates="source")
    subscriptions: Mapped[List["Subscription"]] = relationship(back_populates="source")


class Specialty(Base):
    __tablename__ = "specialties"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    external_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))

    source: Mapped["Source"] = relationship(back_populates="specialties")
    doctors: Mapped[List["Doctor"]] = relationship(back_populates="specialty")
    subscriptions: Mapped[List["Subscription"]] = relationship(back_populates="specialty")


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True)
    specialty_id: Mapped[int] = mapped_column(ForeignKey("specialties.id"))
    external_id: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    room: Mapped[Optional[str]] = mapped_column(String(50))

    specialty: Mapped["Specialty"] = relationship(back_populates="doctors")
    tickets: Mapped[List["Ticket"]] = relationship(back_populates="doctor")
    subscriptions: Mapped[List["Subscription"]] = relationship(back_populates="doctor")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    date: Mapped[date] = mapped_column(Date)
    time: Mapped[dt_time] = mapped_column(Time)
    status: Mapped[str] = mapped_column(String(50), default="available") # available/booked/freed
    first_seen_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    doctor: Mapped["Doctor"] = relationship(back_populates="tickets")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    specialty_id: Mapped[Optional[int]] = mapped_column(ForeignKey("specialties.id"))
    doctor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("doctors.id"))
    date_filter: Mapped[Optional[str]] = mapped_column(String(255))
    time_filter: Mapped[Optional[str]] = mapped_column(String(255))
    event_types: Mapped[Optional[str]] = mapped_column(String(255)) # CSV string of events

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    source: Mapped["Source"] = relationship(back_populates="subscriptions")
    specialty: Mapped["Specialty"] = relationship(back_populates="subscriptions")
    doctor: Mapped["Doctor"] = relationship(back_populates="subscriptions")


class HistoryLog(Base):
    __tablename__ = "history_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(50))
    old_value: Mapped[Optional[str]] = mapped_column(String(255))
    new_value: Mapped[Optional[str]] = mapped_column(String(255))
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow)
