from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import List

from src.db.database import get_db
from src.models.models import User, Currency, Rate, Settings
from src.schemas.schemas import UserCreate, UserUpdate, UserResponse, Token, CurrencyCreate, CurrencyUpdate, CurrencyResponse, RateCreate, RateUpdate, RateResponse, SettingsCreate, SettingsUpdate, SettingsResponse, CoinMarketCapRequest, CurrencyWithRateResponse, IPAccessStatusUpdate, IPAccessStatusResponse
from src.auth.auth import authenticate_user, create_access_token, get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES
from controllers import crud_controller as crud
from controllers.coin_market_cup_controller import get_cryptocurrency_retry_if_empty, replace_symbols_in_result, return_proxy_result
from src.calculate.rate_calc import validate_currency_and_get_rate
from src.middleware.ip_access_control import ip_access_required

import logging

router = APIRouter()

# ── Локальный логгер для роутера ──
logger = logging.getLogger("coinmarket")

# Authentication endpoints
@router.post("/register", response_model=UserResponse, tags=["Authentication"])
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    created_user = crud.create_user(db=db, user=user)
    logger.info("Зарегистрирован новый пользователь: %s", created_user.username)
    return created_user

@router.post("/token", response_model=Token, tags=["Authentication"])
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/users/me", response_model=UserResponse, tags=["Users"])
def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@router.put("/users/me", response_model=UserResponse, tags=["Users"])
def update_user_profile(
    user_update: UserUpdate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update current user's profile (username/password)"""
    result = crud.update_user_profile(
        db=db, 
        user_id=current_user.id, 
        user_update=user_update, 
        current_password=user_update.current_password
    )
    
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    elif result is False:
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    elif result == "username_taken":
        raise HTTPException(status_code=400, detail="Username already exists")
    
    return result

# User CRUD endpoints
@router.get("/users", response_model=List[UserResponse], tags=["Users"])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    users = crud.get_users(db, skip=skip, limit=limit)
    return users

@router.get("/users/{user_id}", response_model=UserResponse, tags=["Users"])
def read_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

# Currency CRUD endpoints
@router.get("/currencies", response_model=List[CurrencyResponse], tags=["Currencies"])
def read_currencies(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    currencies = crud.get_currencies(db, skip=skip, limit=limit)
    return currencies

@router.get("/currencies/rates", response_model=List[CurrencyWithRateResponse], tags=["Currencies"])
def read_currencies_with_rates(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get currencies with their latest activated rates"""
    currencies_with_rates = crud.get_currencies_with_latest_rates(db, skip=skip, limit=limit)
    return currencies_with_rates

@router.post("/currencies", response_model=CurrencyResponse, tags=["Currencies"])
def create_currency(currency: CurrencyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return crud.create_currency(db=db, currency=currency)

@router.patch("/currencies/{currency_code}", response_model=CurrencyResponse, tags=["Currencies"])
def update_currency(currency_code: int, currency_update: CurrencyUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    db_currency = crud.get_currency_by_id(db, currency_id=currency_code)
    if db_currency is None:
        raise HTTPException(status_code=404, detail="Currency not found")
    
    try:
        return crud.update_currency(db=db, currency_id=currency_code, currency_update=currency_update)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/currencies/{currency_code}", tags=["Currencies"])
def delete_currency(currency_code: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    db_currency = crud.get_currency_by_id(db, currency_id=currency_code)
    if db_currency is None:
        raise HTTPException(status_code=404, detail="Currency not found")
    crud.delete_currency(db=db, currency_id=currency_code)
    return {"message": "Currency deleted successfully"}

# Rate CRUD endpoints
@router.get("/currencies/{currency_code}/rates", response_model=List[RateResponse], tags=["Rates"])
def read_currency_rates(currency_code: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # Verify currency exists
    db_currency = crud.get_currency_by_id(db, currency_id=currency_code)
    if db_currency is None:
        raise HTTPException(status_code=404, detail="Currency not found")
    
    rates = crud.get_rates_by_currency(db, currency_id=currency_code, skip=skip, limit=limit)
    return rates

@router.post("/currencies/{currency_code}/rates", response_model=RateResponse, tags=["Rates"])
def create_currency_rate(currency_code: int, rate: RateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    from datetime import datetime
    
    # Verify currency exists
    db_currency = crud.get_currency_by_id(db, currency_id=currency_code)
    if db_currency is None:
        raise HTTPException(status_code=404, detail="Currency not found")
    
    # Validate date_activation is not in the past
    if rate.date_activation:
        # Handle timezone-aware datetime comparison
        current_time = datetime.utcnow()
        rate_time = rate.date_activation
        
        # If rate_time is timezone-aware, convert current_time to timezone-aware
        if rate_time.tzinfo is not None:
            from datetime import timezone
            current_time = current_time.replace(tzinfo=timezone.utc)
        # If rate_time is timezone-naive but current_time is timezone-aware, make both naive
        elif current_time.tzinfo is not None:
            current_time = current_time.replace(tzinfo=None)
            
        if rate_time < current_time:
            raise HTTPException(status_code=400, detail="date_activation cannot be in the past")
    
    # Set custom_curr from currency_code URL parameter
    rate_data = rate.dict()
    rate_data['custom_curr'] = currency_code
    
    db_rate = crud.create_rate(db=db, rate=rate_data)
    if db_rate is None:
        raise HTTPException(status_code=400, detail="date_activation cannot be in the past")
    
    return db_rate

@router.patch("/currencies/{currency_code}/rates/{rate_id}", response_model=RateResponse, tags=["Rates"])
def update_currency_rate(currency_code: int, rate_id: int, rate_update: RateUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    # Verify currency exists
    db_currency = crud.get_currency_by_id(db, currency_id=currency_code)
    if db_currency is None:
        raise HTTPException(status_code=404, detail="Currency not found")
    
    # Verify rate exists
    db_rate = crud.get_rate(db, rate_id=rate_id)
    if db_rate is None:
        raise HTTPException(status_code=404, detail="Rate not found")
    
    # Verify rate belongs to the currency
    if db_rate.custom_curr != currency_code:
        raise HTTPException(status_code=404, detail="Rate not found for this currency")
    
    # Set custom_curr from currency_code URL parameter for update
    update_data = rate_update.dict(exclude_unset=True)
    update_data['custom_curr'] = currency_code
    
    updated_rate = crud.update_rate(db=db, rate_id=rate_id, rate_update=update_data)
    if updated_rate is None:
        raise HTTPException(status_code=400, detail="Cannot modify rate: date_activation has already passed")
    
    return updated_rate

@router.delete("/currencies/{currency_code}/rates/{rate_id}", tags=["Rates"])
def delete_currency_rate(currency_code: int, rate_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    # Verify currency exists
    db_currency = crud.get_currency_by_id(db, currency_id=currency_code)
    if db_currency is None:
        raise HTTPException(status_code=404, detail="Currency not found")
    
    # Verify rate exists
    db_rate = crud.get_rate(db, rate_id=rate_id)
    if db_rate is None:
        raise HTTPException(status_code=404, detail="Rate not found")
    
    # Verify rate belongs to the currency
    if db_rate.custom_curr != currency_code:
        raise HTTPException(status_code=404, detail="Rate not found for this currency")
    
    deleted_rate = crud.delete_rate(db=db, rate_id=rate_id)
    if deleted_rate is None:
        raise HTTPException(status_code=400, detail="Cannot delete rate: date_activation has already passed")
    
    return {"message": "Rate deleted successfully"}

# Settings CRUD endpoints
@router.get("/settings", response_model=List[SettingsResponse], tags=["Settings"])
def read_settings(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Get all settings"""
    settings = crud.get_settings(db, skip=skip, limit=limit)
    return settings

@router.get("/settings/active", response_model=List[SettingsResponse], tags=["Settings"])
def read_active_settings(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Get only active settings"""
    settings = crud.get_active_settings(db, skip=skip, limit=limit)
    return settings

@router.get("/settings/{setting_id}", response_model=SettingsResponse, tags=["Settings"])
def read_setting(setting_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Get setting by ID"""
    db_setting = crud.get_setting_by_id(db, setting_id=setting_id)
    if db_setting is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    return db_setting

@router.get("/settings/name/{setting_name}", response_model=SettingsResponse, tags=["Settings"])
def read_setting_by_name(setting_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Get setting by name"""
    db_setting = crud.get_setting_by_name(db, name=setting_name)
    if db_setting is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    return db_setting

@router.post("/settings", response_model=SettingsResponse, tags=["Settings"])
def create_setting(setting: SettingsCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Create a new setting"""
    # Check if setting with this name already exists
    existing_setting = crud.get_setting_by_name(db, name=setting.name)
    if existing_setting:
        raise HTTPException(status_code=400, detail="Setting with this name already exists")
    
    return crud.create_setting(db=db, setting=setting)

@router.put("/settings/{setting_id}", response_model=SettingsResponse, tags=["Settings"])
def update_setting(setting_id: int, setting_update: SettingsUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Update setting by ID"""
    updated_setting = crud.update_setting(db=db, setting_id=setting_id, setting_update=setting_update)
    if updated_setting is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    return updated_setting

@router.put("/settings/name/{setting_name}", response_model=SettingsResponse, tags=["Settings"])
def update_setting_by_name(setting_name: str, setting_update: SettingsUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Update setting by name"""
    updated_setting = crud.update_setting_by_name(db=db, name=setting_name, setting_update=setting_update)
    if updated_setting is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    return updated_setting

@router.delete("/settings/{setting_id}", tags=["Settings"])
def delete_setting(setting_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Delete setting by ID"""
    deleted_setting = crud.delete_setting(db=db, setting_id=setting_id)
    if deleted_setting is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    return {"message": "Setting deleted successfully"}

@router.delete("/settings/name/{setting_name}", tags=["Settings"])
def delete_setting_by_name(setting_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Delete setting by name"""
    deleted_setting = crud.delete_setting_by_name(db=db, name=setting_name)
    if deleted_setting is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    return {"message": "Setting deleted successfully"}

# IP Access Control endpoints
@router.get("/ip-access/blacklist", tags=["IP Access Control"])
def get_ip_blacklist(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Get current IP blacklist"""
    return crud.get_ip_blacklist(db)

@router.get("/ip-access/whitelist", tags=["IP Access Control"])
def get_ip_whitelist(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Get current IP whitelist"""
    return crud.get_ip_whitelist(db)

@router.put("/ip-access/blacklist", tags=["IP Access Control"])
def update_ip_blacklist(ip_list: List[str], db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Update IP blacklist"""
    crud.update_ip_blacklist(db, ip_list)
    return {"message": "IP blacklist updated successfully", "blacklist": ip_list}

@router.put("/ip-access/whitelist", tags=["IP Access Control"])
def update_ip_whitelist(ip_list: List[str], db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Update IP whitelist"""
    crud.update_ip_whitelist(db, ip_list)
    return {"message": "IP whitelist updated successfully", "whitelist": ip_list}

@router.post("/ip-access/blacklist/{ip}", tags=["IP Access Control"])
def add_ip_to_blacklist(ip: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Add IP to blacklist"""
    crud.add_ip_to_blacklist(db, ip)
    return {"message": f"IP {ip} added to blacklist"}

@router.post("/ip-access/whitelist/{ip}", tags=["IP Access Control"])
def add_ip_to_whitelist(ip: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Add IP to whitelist"""
    crud.add_ip_to_whitelist(db, ip)
    return {"message": f"IP {ip} added to whitelist"}

@router.delete("/ip-access/blacklist/{ip}", tags=["IP Access Control"])
def remove_ip_from_blacklist(ip: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Remove IP from blacklist"""
    crud.remove_ip_from_blacklist(db, ip)
    return {"message": f"IP {ip} removed from blacklist"}

@router.delete("/ip-access/whitelist/{ip}", tags=["IP Access Control"])
def remove_ip_from_whitelist(ip: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Remove IP from whitelist"""
    crud.remove_ip_from_whitelist(db, ip)
    return {"message": f"IP {ip} removed from whitelist"}

# IP Access Control Active Status Management endpoints
@router.put("/ip-access/blacklist/status", response_model=IPAccessStatusResponse, tags=["IP Access Control"])
def set_blacklist_active_status(
    status_update: IPAccessStatusUpdate, 
    request: Request,
    db: Session = Depends(get_db), 
):
    """Set blacklist active status - requires IP access control"""
    try:
        result = crud.set_ip_blacklist_active_status(db, status_update.active)
        return IPAccessStatusResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/ip-access/whitelist/status", response_model=IPAccessStatusResponse, tags=["IP Access Control"])
def set_whitelist_active_status(
    status_update: IPAccessStatusUpdate, 
    request: Request,
    db: Session = Depends(get_db), 
):
    """Set whitelist active status - requires IP access control"""
    try:
        result = crud.set_ip_whitelist_active_status(db, status_update.active)
        return IPAccessStatusResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# CoinMarketCap proxy endpoint
@router.get("/v1/cryptocurrency/quotes/latest", tags=["CoinMarketCap"])
async def get_cryptocurrency_quotes_latest(
    symbol: str,
    convert: str,
    x_cmc_pro_api_key: str = Header(..., alias="X-CMC_PRO_API_KEY"),
    db: Session = Depends(get_db),
    client_ip: str = Depends(ip_access_required)
):
    """Proxy endpoint for CoinMarketCap cryptocurrency quotes"""
    
    # 1) Store parameters in separate variables
    symbol_param = symbol
    convert_param = convert

    # types:
    # 1 - REAL/REAL
    # 2 - REAL/CUSTOM
    # 3 - CUSTOM/REAL
    # 4 - CUSTOM/CUSTOM
    
    # Validate and get final values for both symbol and convert parameters
    symbol_info = validate_currency_and_get_rate(db, symbol_param, "symbol")
    convert_info = validate_currency_and_get_rate(db, convert_param, "convert")
    final_symbol = symbol_info.get('curr')
    final_symbol_price = symbol_info.get('price')
    final_convert = convert_info.get('curr')
    final_convert_price = convert_info.get('price')
    reverse = False
    # Determine type based on whether parameters were substituted
    if symbol_param == final_symbol and convert_param == final_convert:
        type = 1  # REAL/REAL
    elif symbol_param == final_symbol and convert_param != final_convert:
        type = 2  # REAL/CUSTOM
    elif symbol_param != final_symbol and convert_param == final_convert:
        type = 3  # CUSTOM/REAL
    else:  # symbol_param != final_symbol and convert_param != final_convert
        type = 4  # CUSTOM/CUSTOM
    


    headers = {
        "X-CMC_PRO_API_KEY": x_cmc_pro_api_key
    }
    
    helper_resp = await get_cryptocurrency_retry_if_empty(
        symbol=final_symbol,
        convert=final_convert,
        headers=headers,
        db=db
    )
    # merge reverse flag if helper swapped params
    reverse = helper_resp.get('reverse', False) or reverse
    result = helper_resp.get('result', {})

    # Return the response with appropriate status code
    if result.get('status_code') == 200 and result.get('data') and bool(result['data']['data']):
        
        if reverse:
            reversed_price = (1 / result['data']['data'][final_symbol]['quote'][final_convert]['price'])
            result['data']['data'][final_symbol]['quote'][final_convert]['price'] = reversed_price

        if type == 1:
            # Replace symbols in result before returning
            result = replace_symbols_in_result(result, final_symbol, symbol_param, final_convert, convert_param)
        elif type == 2 or type == 3:
            result['data']['data'][final_symbol]['quote'][final_convert]['price'] = (
                final_symbol_price * result['data']['data'][final_symbol]['quote'][final_convert]['price']
            )
            # Replace symbols in result before returning
            result = replace_symbols_in_result(result, final_symbol, symbol_param, final_convert, convert_param)
        elif type == 4:
            result['data']['data'][final_symbol]['quote'][final_convert]['price'] = (
                (result['data']['data'][final_symbol]['quote'][final_convert]['price'] * final_symbol_price) * (1 / final_convert_price)
            )
            # Replace symbols in result before returning
            result = replace_symbols_in_result(result, final_symbol, symbol_param, final_convert, convert_param)

    # Always return the result through return_proxy_result
    return return_proxy_result(result)
