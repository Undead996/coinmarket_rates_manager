import os
import logging
import httpx
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import Response
from src.cache.cache import get_cache_key, get_caching_time, get_from_cache, store_in_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('coinmarketcap_proxy.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Get base URL from environment
BASE_URL = os.getenv('COINMARKETCAP_HOST', 'https://pro-api.coinmarketcap.com')

def return_proxy_result(result: Dict[str, Any]) -> Response:
    """
    Return a proxy result with proper HTTP response structure
    
    Args:
        result: Dict containing status_code, headers, and data
        
    Returns:
        FastAPI Response with proper status code, headers, and body
    """
    import json
    
    status_code = result.get('status_code', 200)
    original_headers = result.get('headers', {})
    data = result.get('data', {})
    
    # Filter out problematic headers that could cause conflicts
    filtered_headers = {}
    headers_to_exclude = {
        'content-length', 'content-encoding', 'transfer-encoding', 
        'connection', 'server', 'date'
    }
    
    for key, value in original_headers.items():
        if key.lower() not in headers_to_exclude:
            filtered_headers[key] = value
    
    # Convert data to JSON string for response body
    content = json.dumps(data)
    
    # Create FastAPI Response with proper status code and headers
    return Response(
        content=content,
        status_code=status_code,
        headers=filtered_headers,
        media_type="application/json"
    )

def replace_symbols_in_result(result: dict, final_symbol: str, symbol: str, final_convert: str, convert: str) -> dict:
    """
    Replace final_symbol with symbol and final_convert with convert in the result data structure.
    Modifies the nested dictionary structure: result['data']['data'][final_symbol]['quote'][final_convert]
    """
    if (result.get('data') and 
        result['data'].get('data') and 
        final_symbol in result['data']['data'] and
        result['data']['data'][final_symbol].get('quote') and
        final_convert in result['data']['data'][final_symbol]['quote']):
        
        # Copy all content from final_symbol to symbol
        result['data']['data'][symbol] = result['data']['data'][final_symbol].copy()
        
        # Update the symbol field to match the original parameter
        if 'symbol' in result['data']['data'][symbol]:
            result['data']['data'][symbol]['symbol'] = symbol
            
        # Handle quote conversion renaming
        if final_convert != convert and 'quote' in result['data']['data'][symbol]:
            if final_convert in result['data']['data'][symbol]['quote']:
                # Move the quote data from final_convert to convert
                result['data']['data'][symbol]['quote'][convert] = result['data']['data'][symbol]['quote'][final_convert]
                del result['data']['data'][symbol]['quote'][final_convert]
        
        # Remove the original final_symbol entry
        if final_symbol != symbol:
            del result['data']['data'][final_symbol]
    
    return result

async def get_cryptocurrency(
    symbol: str, 
    convert: str,
    headers: Dict[str, Any],
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Proxy request to CoinMarketCap API for cryptocurrency quotes with caching
    
    Args:
        symbol: Cryptocurrency symbol (e.g., 'BTC,ETH')
        convert: Convert currency (e.g., 'USD')
        headers: Request headers from the original request
        db: Database session for checking cache settings
        
    Returns:
        Dict containing the API response
    """
    
    # Check cache first
    cache_key = get_cache_key(symbol, convert)
    cached_result = get_from_cache(cache_key)
    if cached_result:
        return cached_result.get('data')
    
    # Prepare request parameters
    params = {
        'symbol': symbol,
        'convert': convert
    }
    
    # Prepare headers for the external API call
    api_headers = {}
    
    # Forward relevant headers (you might want to add API key here)
    if 'X-CMC_PRO_API_KEY' in headers:
        api_headers['X-CMC_PRO_API_KEY'] = headers['X-CMC_PRO_API_KEY']
    
    # Set default headers
    api_headers.update({
        'Accept': 'application/json',
        'Accept-Encoding': 'deflate, gzip'
    })
    
    try:
        # Make request to CoinMarketCap API
        url = f"{BASE_URL}/v1/cryptocurrency/quotes/latest"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers=api_headers,
                timeout=30.0
            )
            
            # # Log outgoing request details
            # logger.info(f"=== OUTGOING REQUEST ===")
            # logger.info(f"URL: {url}")
            # logger.info(f"Params: {params}")
            # logger.info(f"Headers sent: {api_headers}")
            
            # # Log response details
            # logger.info(f"=== RESPONSE ===")
            # logger.info(f"Status code: {response.status_code}")
            # logger.info(f"Response headers: {dict(response.headers)}")
            
            # Get response data
            response_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
            
            # logger.info(f"Response data preview: {str(response_data)[:500]}...")
            
            # Prepare response
            result = {
                'status_code': response.status_code,
                'headers': dict(response.headers),
                'data': response_data
            }
            
            # Cache successful responses
            if response.status_code == 200 and response_data.get('data') and db:
                cache_time = get_caching_time(db)
                store_in_cache(cache_key, result, cache_time)
            
            return result
            
    except httpx.TimeoutException:
        # logger.error("Request timeout to CoinMarketCap API")
        return {
            'status_code': 408,
            'headers': {},
            'data': {'error': 'Request timeout'}
        }
    except httpx.RequestError as e:
        # logger.error(f"Request error: {str(e)}")
        return {
            'status_code': 500,
            'headers': {},
            'data': {'error': f'Request failed: {str(e)}'}
        }


async def get_cryptocurrency_retry_if_empty(
    symbol: str,
    convert: str,
    headers: Dict[str, Any],
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Call get_cryptocurrency. If status is 200 but payload is empty, swap symbol/convert and retry once.
    Returns a dict with keys: 'result' (the final response dict) and 'reverse' (bool, whether swap was performed).
    """
    reverse = False
    result = await get_cryptocurrency(symbol=symbol, convert=convert, headers=headers, db=db)

    def _is_empty_payload(obj: Any) -> bool:
        if isinstance(obj, dict):
            if 'data' in obj:
                return not bool(obj.get('data'))
            return not bool(obj)
        if obj is None:
            return True
        if hasattr(obj, '__len__'):
            try:
                return len(obj) == 0
            except Exception:
                return False
        return False

    if result.get('status_code') == 200 and _is_empty_payload(result.get('data')):
        logger.info("Empty payload on first try; swapping symbol/convert and retrying once")
        symbol, convert = convert, symbol
        reverse = True
        result = await get_cryptocurrency(symbol=symbol, convert=convert, headers=headers, db=db)

    return {"result": result, "reverse": reverse}
