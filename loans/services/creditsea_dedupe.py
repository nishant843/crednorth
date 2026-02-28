"""
CreditSea dedupe checking module.
"""

import requests
from typing import Optional


CREDITSEA_API_KEY = "cs_dedupe_9f3a8b2c7e4d1a6f5c0b8e2a91d4f7c6"


def check_creditsea_dedupe(phoneNumber: Optional[str], panNumber: Optional[str]) -> dict:
    """
    Check dedupe status with CreditSea API.
    
    Args:
        phoneNumber: Phone number (can be None)
        panNumber: PAN card number (can be None)
    
    Returns:
        Dictionary with normalized response:
        - {"status": "SUCCESS", "result": "DUPLICATE"} - User exists (duplicate)
        - {"status": "SUCCESS", "result": "NOT_DUPLICATE"} - User not found
        - {"status": "FAILED", "result": "API_ERROR"} - Network or API error
    """
    url = "https://backend.creditsea.com/api/v1/dsa/check-dedupe"
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": CREDITSEA_API_KEY
    }
    
    payload = {
        "phoneNumber": phoneNumber,
        "panNumber": panNumber
    }
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        response.raise_for_status()
        
        data = response.json()
        
        success = data.get("success")
        dedupe = data.get("dedupe")
        
        if success is True and dedupe is True:
            return {
                "status": "SUCCESS",
                "result": "DUPLICATE"
            }
        
        if success is True and dedupe is False:
            return {
                "status": "SUCCESS",
                "result": "NOT_DUPLICATE"
            }
        
        return {
            "status": "FAILED",
            "result": "API_ERROR"
        }
        
    except Exception:
        return {
            "status": "FAILED",
            "result": "API_ERROR"
        }
