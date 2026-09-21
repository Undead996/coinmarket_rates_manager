import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
 
# In-memory cache for storing API responses
_cache = {}

def get_cache_key(symbol: str, convert: str) -> str:
    """Generate a cache key for the given symbol and convert parameters"""
    return hashlib.md5(f"{symbol}:{convert}".encode()).hexdigest()

def get_caching_time(db: Session) -> int:
    """Get caching time from settings table"""
    try:
        from src.models.models import Settings
        setting = db.query(Settings).filter(
            Settings.name == "caching_time",
            Settings.active == True
        ).first()
        
        if setting and setting.value.isdigit():
            return int(setting.value)
    except Exception as e:
        logger.warning(f"Error getting caching time from settings: {e}")
    
    return 300  # Default 300 seconds

def is_cache_valid(cache_entry: Dict[str, Any]) -> bool:
    """Check if cache entry is still valid"""
    if 'timestamp' not in cache_entry or 'expires_at' not in cache_entry:
        return False
    
    return datetime.now() < cache_entry['expires_at']

def get_from_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    """Get data from cache if valid"""
    if cache_key in _cache:
        cache_entry = _cache[cache_key]
        if is_cache_valid(cache_entry):
            logger.info(f"Cache hit for key: {cache_key}")
            return cache_entry['data']
        else:
            # Remove expired entry
            del _cache[cache_key]
            logger.info(f"Cache expired for key: {cache_key}")
    
    return None

def store_in_cache(cache_key: str, data: Dict[str, Any], cache_time: int):
    """Store data in cache with expiration"""
    _cache[cache_key] = {
        'data': data,
        'timestamp': datetime.now(),
        'expires_at': datetime.now() + timedelta(seconds=cache_time)
    }
    logger.info(f"Stored in cache for {cache_time} seconds, key: {cache_key}")
