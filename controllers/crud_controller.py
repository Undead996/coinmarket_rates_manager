from sqlalchemy.orm import Session
from src.models.models import User, Currency, Rate, Settings
from src.schemas.schemas import UserCreate, CurrencyCreate, CurrencyUpdate, RateCreate, RateUpdate, SettingsCreate, SettingsUpdate
from src.auth.auth import get_password_hash

def _compare_datetimes(dt1, dt2):
    """Helper function to compare datetimes handling timezone awareness"""
    from datetime import timezone
    
    # Make both datetimes timezone-aware or timezone-naive for comparison
    if dt1.tzinfo is not None and dt2.tzinfo is None:
        dt2 = dt2.replace(tzinfo=timezone.utc)
    elif dt1.tzinfo is None and dt2.tzinfo is not None:
        dt2 = dt2.replace(tzinfo=None)
    
    return dt1 < dt2

# User CRUD operations
def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()



def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(User).offset(skip).limit(limit).all()

def create_user(db: Session, user: UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_profile(db: Session, user_id: int, user_update, current_password: str):
    """Update user profile (username/password) with current password verification"""
    from src.auth.auth import verify_password, get_password_hash
    
    # Get the user
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    # Verify current password
    if not verify_password(current_password, db_user.hashed_password):
        return False  # Invalid current password
    
    # Check if new username is already taken (if username is being changed)
    if hasattr(user_update, 'username') and user_update.username:
        if user_update.username != db_user.username:
            existing_user = get_user_by_username(db, user_update.username)
            if existing_user:
                return "username_taken"
    
    # Update fields
    if hasattr(user_update, 'username') and user_update.username:
        db_user.username = user_update.username
    
    if hasattr(user_update, 'password') and user_update.password:
        db_user.hashed_password = get_password_hash(user_update.password)
    
    db.commit()
    db.refresh(db_user)
    return db_user

# Currency CRUD operations
def get_currency_by_id(db: Session, currency_id: int):
    return db.query(Currency).filter(Currency.id == currency_id).first()

def get_currencies(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Currency).offset(skip).limit(limit).all()

def get_currencies_with_latest_rates(db: Session, skip: int = 0, limit: int = 100):
    """Get currencies with their latest activated rates"""
    from sqlalchemy import and_, func
    from datetime import datetime
    
    # Subquery to get the latest date_activation for each currency that has already been activated
    latest_rates_subquery = db.query(
        Rate.custom_curr,
        func.max(Rate.date_activation).label('latest_activation')
    ).filter(
        Rate.date_activation <= datetime.utcnow()
    ).group_by(Rate.custom_curr).subquery()
    
    # Main query to get currencies with their latest rate information
    result = db.query(
        Currency,
        Rate.bind_curr,
        Rate.price,
        Rate.date_created,
        Rate.date_activation
    ).outerjoin(
        latest_rates_subquery,
        Currency.id == latest_rates_subquery.c.custom_curr
    ).outerjoin(
        Rate,
        and_(
            Rate.custom_curr == Currency.id,
            Rate.date_activation == latest_rates_subquery.c.latest_activation
        )
    ).offset(skip).limit(limit).all()
    
    # Convert to list of dictionaries for easier handling
    currencies_with_rates = []
    for row in result:
        currency = row[0]
        currency_dict = {
            'id': currency.id,
            'name': currency.name,
            'symbol': currency.symbol,
            'slug': currency.slug,
            'bind_curr_ticker': currency.bind_curr_ticker,
            'cmc_rank': currency.cmc_rank,
            'circulating_supply': currency.circulating_supply,
            'total_supply': currency.total_supply,
            'max_supply': currency.max_supply,
            'infinite_supply': currency.infinite_supply,
            'active': currency.active,
            'tags': currency.tags,
            'date_added': currency.date_added,
            'last_updated': currency.last_updated,
            'bind_curr': row[1],
            'price': row[2],
            'date_created': row[3],
            'date_activation': row[4]
        }
        currencies_with_rates.append(currency_dict)
    
    return currencies_with_rates

def create_currency(db: Session, currency: CurrencyCreate):
    db_currency = Currency(**currency.dict())
    db.add(db_currency)
    db.commit()
    db.refresh(db_currency)
    return db_currency

def update_currency(db: Session, currency_id: int, currency_update: CurrencyUpdate):
    from datetime import datetime
    
    db_currency = db.query(Currency).filter(Currency.id == currency_id).first()
    if not db_currency:
        return None
    
    # Check if there are any rates with activated date_activation
    current_time = datetime.utcnow()
    activated_rates = db.query(Rate).filter(
        Rate.custom_curr == currency_id,
        Rate.date_activation <= current_time
    ).first()
    
    if activated_rates:
        # Return a special error indicator that the router can catch
        raise ValueError("Cannot update currency: rates with activated date_activation exist")
    
    update_data = currency_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_currency, field, value)
    db.commit()
    db.refresh(db_currency)
    return db_currency

def delete_currency(db: Session, currency_id: int):
    db_currency = db.query(Currency).filter(Currency.id == currency_id).first()
    if db_currency:
        # First delete all related rates
        db.query(Rate).filter(Rate.custom_curr == currency_id).delete()
        # Then delete the currency
        db.delete(db_currency)
        db.commit()
    return db_currency

# Rate CRUD operations
def get_rates_by_currency(db: Session, currency_id: int, skip: int = 0, limit: int = 100):
    return db.query(Rate).filter(
        Rate.custom_curr == currency_id
    ).offset(skip).limit(limit).all()

def get_rate(db: Session, rate_id: int):
    return db.query(Rate).filter(Rate.id == rate_id).first()

def create_rate(db: Session, rate):
    from datetime import datetime
    
    # Handle both RateCreate object and dictionary
    if hasattr(rate, 'dict'):
        rate_data = rate.dict()
    else:
        rate_data = rate
    
    # Get currency to set bind_curr from bind_curr_ticker
    currency = db.query(Currency).filter(Currency.id == rate_data['custom_curr']).first()
    if not currency:
        return None  # Currency not found
    
    # Set bind_curr from currency's bind_curr_ticker
    rate_data['bind_curr'] = currency.bind_curr_ticker
    
    # Set date_activation to current time if not provided
    if rate_data.get('date_activation') is None:
        rate_data['date_activation'] = datetime.utcnow()
    
    # Validate that date_activation is not in the past
    current_time = datetime.utcnow()
    rate_time = rate_data['date_activation']
    
    # Handle timezone-aware datetime comparison
    if rate_time.tzinfo is not None:
        from datetime import timezone
        current_time = current_time.replace(tzinfo=timezone.utc)
    elif current_time.tzinfo is not None:
        current_time = current_time.replace(tzinfo=None)
        
    if rate_time < current_time:
        return None  # Will be handled in the endpoint
    
    db_rate = Rate(**rate_data)
    db.add(db_rate)
    db.commit()
    db.refresh(db_rate)
    return db_rate

def update_rate(db: Session, rate_id: int, rate_update):
    from datetime import datetime
    
    db_rate = db.query(Rate).filter(Rate.id == rate_id).first()
    if db_rate:
        # Check if date_activation has already passed
        if _compare_datetimes(db_rate.date_activation, datetime.utcnow()):
            return None  # Will be handled in the endpoint
        
        # Handle both RateUpdate object and dictionary
        if hasattr(rate_update, 'dict'):
            update_data = rate_update.dict(exclude_unset=True)
        else:
            update_data = rate_update
        
        # If custom_curr is being updated, set bind_curr from new currency's bind_curr_ticker
        if 'custom_curr' in update_data:
            currency = db.query(Currency).filter(Currency.id == update_data['custom_curr']).first()
            if not currency:
                return None  # Currency not found
            update_data['bind_curr'] = currency.bind_curr_ticker
        
        # Validate date_activation if being updated
        if 'date_activation' in update_data:
            current_time = datetime.utcnow()
            new_time = update_data['date_activation']
            
            # Handle timezone-aware datetime comparison
            if new_time.tzinfo is not None:
                from datetime import timezone
                current_time = current_time.replace(tzinfo=timezone.utc)
            elif current_time.tzinfo is not None:
                current_time = current_time.replace(tzinfo=None)
                
            if new_time < current_time:
                return None  # Will be handled in the endpoint
        
        for field, value in update_data.items():
            setattr(db_rate, field, value)
        db.commit()
        db.refresh(db_rate)
    return db_rate

def delete_rate(db: Session, rate_id: int):
    from datetime import datetime
    
    db_rate = db.query(Rate).filter(Rate.id == rate_id).first()
    if db_rate:
        # Check if date_activation has already passed
        if _compare_datetimes(db_rate.date_activation, datetime.utcnow()):
            return None  # Will be handled in the endpoint
        
        db.delete(db_rate)
        db.commit()
    return db_rate

# Settings CRUD operations
def get_setting_by_id(db: Session, setting_id: int):
    return db.query(Settings).filter(Settings.id == setting_id).first()

def get_setting_by_name(db: Session, name: str):
    return db.query(Settings).filter(Settings.name == name).first()

def get_settings(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Settings).offset(skip).limit(limit).all()

def get_active_settings(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Settings).filter(Settings.active == True).offset(skip).limit(limit).all()

def create_setting(db: Session, setting: SettingsCreate):
    db_setting = Settings(**setting.dict())
    db.add(db_setting)
    db.commit()
    db.refresh(db_setting)
    return db_setting

def update_setting(db: Session, setting_id: int, setting_update: SettingsUpdate):
    db_setting = db.query(Settings).filter(Settings.id == setting_id).first()
    if db_setting:
        update_data = setting_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_setting, field, value)
        db.commit()
        db.refresh(db_setting)
    return db_setting

def update_setting_by_name(db: Session, name: str, setting_update: SettingsUpdate):
    db_setting = db.query(Settings).filter(Settings.name == name).first()
    if db_setting:
        update_data = setting_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_setting, field, value)
        db.commit()
        db.refresh(db_setting)
    return db_setting

def delete_setting(db: Session, setting_id: int):
    db_setting = db.query(Settings).filter(Settings.id == setting_id).first()
    if db_setting:
        db.delete(db_setting)
        db.commit()
    return db_setting

def delete_setting_by_name(db: Session, name: str):
    db_setting = db.query(Settings).filter(Settings.name == name).first()
    if db_setting:
        db.delete(db_setting)
        db.commit()
    return db_setting

# IP Access Control CRUD operations
import json
from typing import List

def get_ip_blacklist(db: Session) -> dict:
    """Get IP blacklist from settings"""
    setting = get_setting_by_name(db, "black_list_ip")
    if setting:
        try:
            ip_list = json.loads(setting.value) if setting.active else []
            return {
                "blacklist": ip_list,
                "active": setting.active
            }
        except json.JSONDecodeError:
            return {
                "blacklist": [],
                "active": setting.active
            }
    return {
        "blacklist": [],
        "active": False
    }

def get_ip_whitelist(db: Session) -> dict:
    """Get IP whitelist from settings"""
    setting = get_setting_by_name(db, "white_list_ip")
    if setting:
        try:
            ip_list = json.loads(setting.value) if setting.active else []
            return {
                "whitelist": ip_list,
                "active": setting.active
            }
        except json.JSONDecodeError:
            return {
                "whitelist": [],
                "active": setting.active
            }
    return {
        "whitelist": [],
        "active": False
    }

def update_ip_blacklist(db: Session, ip_list: List[str]) -> Settings:
    """Update IP blacklist in settings"""
    from src.schemas.schemas import SettingsCreate, SettingsUpdate
    
    setting = get_setting_by_name(db, "black_list_ip")
    ip_json = json.dumps(ip_list)
    
    if setting:
        # Update existing setting
        setting_update = SettingsUpdate(value=ip_json, active=True)
        return update_setting_by_name(db, "black_list_ip", setting_update)
    else:
        # Create new setting
        setting_create = SettingsCreate(
            name="black_list_ip",
            value=ip_json,
            active=True
        )
        return create_setting(db, setting_create)

def update_ip_whitelist(db: Session, ip_list: List[str]) -> Settings:
    """Update IP whitelist in settings"""
    from src.schemas.schemas import SettingsCreate, SettingsUpdate
    
    setting = get_setting_by_name(db, "white_list_ip")
    ip_json = json.dumps(ip_list)
    
    if setting:
        # Update existing setting
        setting_update = SettingsUpdate(value=ip_json, active=True)
        return update_setting_by_name(db, "white_list_ip", setting_update)
    else:
        # Create new setting
        setting_create = SettingsCreate(
            name="white_list_ip",
            value=ip_json,
            active=True
        )
        return create_setting(db, setting_create)

def add_ip_to_blacklist(db: Session, ip: str) -> Settings:
    """Add IP to blacklist"""
    blacklist_data = get_ip_blacklist(db)
    blacklist = blacklist_data["blacklist"]
    if ip not in blacklist:
        blacklist.append(ip)
    return update_ip_blacklist(db, blacklist)

def add_ip_to_whitelist(db: Session, ip: str) -> Settings:
    """Add IP to whitelist"""
    whitelist_data = get_ip_whitelist(db)
    whitelist = whitelist_data["whitelist"]
    if ip not in whitelist:
        whitelist.append(ip)
    return update_ip_whitelist(db, whitelist)

def remove_ip_from_blacklist(db: Session, ip: str) -> Settings:
    """Remove IP from blacklist"""
    blacklist_data = get_ip_blacklist(db)
    blacklist = blacklist_data["blacklist"]
    if ip in blacklist:
        blacklist.remove(ip)
    return update_ip_blacklist(db, blacklist)

def remove_ip_from_whitelist(db: Session, ip: str) -> Settings:
    """Remove IP from whitelist"""
    whitelist_data = get_ip_whitelist(db)
    whitelist = whitelist_data["whitelist"]
    if ip in whitelist:
        whitelist.remove(ip)
    return update_ip_whitelist(db, whitelist)

def is_ip_allowed(db: Session, client_ip: str) -> bool:
    """Check if IP is allowed based on black/white lists"""
    # Get blacklist setting
    blacklist_setting = get_setting_by_name(db, "black_list_ip")
    blacklist = []
    if blacklist_setting and blacklist_setting.active:
        try:
            blacklist = json.loads(blacklist_setting.value)
        except json.JSONDecodeError:
            blacklist = []
    
    # Get whitelist setting
    whitelist_setting = get_setting_by_name(db, "white_list_ip")
    whitelist = []
    if whitelist_setting and whitelist_setting.active:
        try:
            whitelist = json.loads(whitelist_setting.value)
        except json.JSONDecodeError:
            whitelist = []
    
    # If blacklist is active and IP is in blacklist, deny access
    if blacklist and client_ip in blacklist:
        return False
    
    # If whitelist is active and not empty, only allow IPs in whitelist
    if whitelist:
        return client_ip in whitelist
    
    # If no active restrictions, allow access
    return True

def set_ip_blacklist_active_status(db: Session, active: bool) -> dict:
    """Set blacklist active status with validation"""
    from src.schemas.schemas import SettingsCreate, SettingsUpdate
    
    # Check if whitelist is currently active
    whitelist_setting = get_setting_by_name(db, "white_list_ip")
    if active and whitelist_setting and whitelist_setting.active:
        raise ValueError("Cannot activate blacklist: whitelist is currently active")
    
    # Get or create blacklist setting
    blacklist_setting = get_setting_by_name(db, "black_list_ip")
    
    if blacklist_setting:
        # Update existing setting
        setting_update = SettingsUpdate(active=active)
        updated_setting = update_setting_by_name(db, "black_list_ip", setting_update)
        return {
            "name": "black_list_ip",
            "active": updated_setting.active,
            "message": f"Blacklist {'activated' if active else 'deactivated'} successfully"
        }
    else:
        # Create new setting if it doesn't exist
        setting_create = SettingsCreate(
            name="black_list_ip",
            value="[]",  # Empty list by default
            active=active
        )
        created_setting = create_setting(db, setting_create)
        return {
            "name": "black_list_ip",
            "active": created_setting.active,
            "message": f"Blacklist created and {'activated' if active else 'deactivated'} successfully"
        }

def set_ip_whitelist_active_status(db: Session, active: bool) -> dict:
    """Set whitelist active status with validation"""
    from src.schemas.schemas import SettingsCreate, SettingsUpdate
    
    # Check if blacklist is currently active
    blacklist_setting = get_setting_by_name(db, "black_list_ip")
    if active and blacklist_setting and blacklist_setting.active:
        raise ValueError("Cannot activate whitelist: blacklist is currently active")
    
    # Get or create whitelist setting
    whitelist_setting = get_setting_by_name(db, "white_list_ip")
    
    if whitelist_setting:
        # Update existing setting
        setting_update = SettingsUpdate(active=active)
        updated_setting = update_setting_by_name(db, "white_list_ip", setting_update)
        return {
            "name": "white_list_ip",
            "active": updated_setting.active,
            "message": f"Whitelist {'activated' if active else 'deactivated'} successfully"
        }
    else:
        # Create new setting if it doesn't exist
        setting_create = SettingsCreate(
            name="white_list_ip",
            value="[]",  # Empty list by default
            active=active
        )
        created_setting = create_setting(db, setting_create)
        return {
            "name": "white_list_ip",
            "active": created_setting.active,
            "message": f"Whitelist created and {'activated' if active else 'deactivated'} successfully"
        }
