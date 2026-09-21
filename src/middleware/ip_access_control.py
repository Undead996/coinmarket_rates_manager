"""
IP Access Control Middleware
Provides IP-based access control using black and white lists from settings
"""

from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from src.db.database import get_db
from controllers.crud_controller import is_ip_allowed
import ipaddress

def get_client_ip(request: Request) -> str:
    """Extract client IP from request"""
    # Check for forwarded headers first (for proxy/load balancer scenarios)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fallback to direct client IP
    if request.client:
        return request.client.host
    
    return "unknown"

def validate_ip_format(ip: str) -> bool:
    """Validate IP address format"""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def check_ip_access(request: Request, db: Session = Depends(get_db)):
    """
    Middleware dependency to check IP access
    Raises HTTPException if IP is not allowed
    """
    client_ip = get_client_ip(request)
    
    # Skip validation for unknown IPs (localhost scenarios)
    if client_ip == "unknown":
        return client_ip
    
    # Validate IP format
    if not validate_ip_format(client_ip):
        raise HTTPException(
            status_code=403,
            detail="Invalid IP address format"
        )
    
    # Check if IP is allowed
    if not is_ip_allowed(db, client_ip):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied for IP: {client_ip}"
        )
    
    return client_ip

def ip_access_required(request: Request, db: Session = Depends(get_db)) -> str:
    """
    Dependency function for endpoints that require IP access control
    Returns the client IP if allowed, raises HTTPException if denied
    """
    return check_ip_access(request, db)
