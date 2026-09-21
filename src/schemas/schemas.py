from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# User schemas
class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    current_password: str  # Required to verify identity

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Auth schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Currency schemas
class CurrencyBase(BaseModel):
    name: str
    symbol: str
    slug: str
    bind_curr_ticker: str
    cmc_rank: Optional[int] = None
    circulating_supply: Optional[float] = None
    total_supply: Optional[float] = None
    max_supply: Optional[float] = None
    infinite_supply: Optional[bool] = False
    active: Optional[bool] = False
    tags: Optional[str] = None

class CurrencyCreate(CurrencyBase):
    pass

class CurrencyUpdate(BaseModel):
    name: Optional[str] = None
    symbol: Optional[str] = None
    slug: Optional[str] = None
    bind_curr_ticker: Optional[str] = None
    cmc_rank: Optional[int] = None
    circulating_supply: Optional[float] = None
    total_supply: Optional[float] = None
    max_supply: Optional[float] = None
    infinite_supply: Optional[bool] = None
    active: Optional[bool] = None
    tags: Optional[str] = None

class CurrencyResponse(CurrencyBase):
    id: int
    date_added: datetime
    last_updated: Optional[datetime] = None

    class Config:
        from_attributes = True

# Rate schemas
class RateBase(BaseModel):
    price: float
    volume_24h: Optional[float] = 0
    volume_change_24h: Optional[float] = 0
    percent_change_1h: Optional[float] = 0
    percent_change_24h: Optional[float] = 0
    percent_change_7d: Optional[float] = 0
    market_cap: Optional[float] = 0
    market_cap_dominance: Optional[float] = 0
    fully_diluted_market_cap: Optional[float] = 0
    date_activation: Optional[datetime] = None

class RateCreate(RateBase):
    pass

class RateUpdate(BaseModel):
    price: Optional[float] = None
    volume_24h: Optional[float] = None
    volume_change_24h: Optional[float] = None
    percent_change_1h: Optional[float] = None
    percent_change_24h: Optional[float] = None
    percent_change_7d: Optional[float] = None
    market_cap: Optional[float] = None
    market_cap_dominance: Optional[float] = None
    fully_diluted_market_cap: Optional[float] = None
    date_activation: Optional[datetime] = None

class RateResponse(RateBase):
    id: int
    custom_curr: int
    bind_curr: str
    date_created: datetime

    class Config:
        from_attributes = True

# Settings schemas
class SettingsBase(BaseModel):
    name: str
    value: str
    active: Optional[bool] = False

class SettingsCreate(SettingsBase):
    pass

class SettingsUpdate(BaseModel):
    name: Optional[str] = None
    value: Optional[str] = None
    active: Optional[bool] = None

class SettingsResponse(SettingsBase):
    id: int

    class Config:
        from_attributes = True

# Currency with latest rate schema
class CurrencyWithRateResponse(CurrencyBase):
    id: int
    date_added: datetime
    last_updated: Optional[datetime] = None
    # Latest rate fields
    bind_curr: Optional[str] = None
    price: Optional[float] = None
    date_created: Optional[datetime] = None
    date_activation: Optional[datetime] = None

    class Config:
        from_attributes = True

# IP Access Control schemas
class IPAccessStatusUpdate(BaseModel):
    active: bool

class IPAccessStatusResponse(BaseModel):
    name: str
    active: bool
    message: str

# CoinMarketCap schemas
class CoinMarketCapRequest(BaseModel):
    symbol: str
    convert: str
    x_cmc_pro_api_key: str
    
    class Config:
        # Allow field aliases for headers
        populate_by_name = True
        
