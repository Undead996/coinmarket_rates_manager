from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from src.models.models import Currency, Rate


def validate_currency_and_get_rate(db: Session, currency_symbol: str, param_name: str):
    """
    Validate currency and get active rate
    
    Args:
        db: Database session
        currency_symbol: Currency symbol to validate
        param_name: Parameter name for error messages
    
    Returns:
        str: Original symbol or bind_curr from active rate
    
    Raises:
        HTTPException: If currency is not active or no active rate found
    """
    # Check if currency exists in currencies table
    currency = db.query(Currency).filter(Currency.symbol == currency_symbol).first()
    
    if currency:
        # Check if currency is active
        if not currency.active:
            raise HTTPException(
                status_code=400, 
                detail=f"Currency {currency_symbol} is not active"
            )
        
        # Find latest rate with passed date_activation
        current_time = datetime.utcnow()
        
        # Get rates ordered by date_created descending to find the latest record first
        rates = db.query(Rate).filter(
            Rate.custom_curr == currency.id
        ).order_by(Rate.date_created.desc()).all()
        
        if rates:
            # Find the latest rate with passed date_activation
            for rate in rates:
                if rate.date_activation <= current_time:
                    # Return bind currency and the full Rate ORM object
                    return {"curr": rate.bind_curr, "price": rate.price}
            
            # If no rate found with passed date_activation, raise error
            raise HTTPException(
                status_code=400,
                detail=f"No active rate found for currency {currency_symbol}"
            )
    
    # Return original symbol if not found in currencies table
    return {"curr": currency_symbol, "price": None}
