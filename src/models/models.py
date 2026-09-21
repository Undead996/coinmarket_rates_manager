from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from src.db.database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)





class Currency(Base):
    __tablename__ = "currencies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    symbol = Column(String(10), nullable=False, index=True)
    slug = Column(String(100), nullable=False, index=True)
    bind_curr_ticker = Column(String(10), nullable=False, index=True)
    cmc_rank = Column(Integer, nullable=True)
    circulating_supply = Column(Float, nullable=True)
    total_supply = Column(Float, nullable=True)
    max_supply = Column(Float, nullable=True)
    infinite_supply = Column(Boolean, default=False, nullable=False)
    active = Column(Boolean, default=False, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
    date_added = Column(DateTime, nullable=False, default=datetime.utcnow)
    tags = Column(Text, nullable=True)  # JSON string

class Rate(Base):
    __tablename__ = "rates"

    id = Column(Integer, primary_key=True, index=True)
    custom_curr = Column(Integer, ForeignKey("currencies.id"), nullable=False, index=True)
    bind_curr = Column(String(10), nullable=False, index=True)
    price = Column(Float, nullable=False)
    volume_24h = Column(Float, default=0, nullable=True)
    volume_change_24h = Column(Float, default=0, nullable=True)
    percent_change_1h = Column(Float, default=0, nullable=True)
    percent_change_24h = Column(Float, default=0, nullable=True)
    percent_change_7d = Column(Float, default=0, nullable=True)
    market_cap = Column(Float, default=0, nullable=True)
    market_cap_dominance = Column(Float, default=0, nullable=True)
    fully_diluted_market_cap = Column(Float, default=0, nullable=True)
    date_created = Column(DateTime, nullable=False, default=datetime.utcnow)
    date_activation = Column(DateTime, nullable=False, index=True)

    # Relationship to Currency table (only for custom_curr)
    currency_from = relationship("Currency", foreign_keys=[custom_curr])

class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(String(500), nullable=False)
    active = Column(Boolean, nullable=False, default=False)
