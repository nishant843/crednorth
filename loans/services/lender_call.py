"""
Lender API call module for dedupe checking.
Handles individual user checks against specific lenders.
"""

from typing import Optional
from .creditsea_dedupe import check_creditsea_dedupe
from .creditsea_lead import create_creditsea_lead


def process_lender(
    lender_name: str, 
    row_data: dict, 
    check_dedupe: bool, 
    send_leads: bool
) -> dict:
    """
    Route lead processing to appropriate lender.
    
    Args:
        lender_name: Name of the lender
        row_data: Full CSV row dictionary with all fields
        check_dedupe: Whether to perform dedupe check
        send_leads: Whether to create lead
    
    Returns:
        Dictionary with normalized response
    """
    if not check_dedupe and not send_leads:
        return {
            "status": "FAILED",
            "result": "NO_ACTION_SELECTED"
        }
    
    lender_lower = lender_name.lower()
    
    if lender_lower == "creditsea":
        return _process_creditsea(row_data, check_dedupe, send_leads)
    
    return {
        "status": "FAILED",
        "result": "UNSUPPORTED_LENDER"
    }


def _process_creditsea(row_data: dict, check_dedupe: bool, send_leads: bool) -> dict:
    """
    Process CreditSea workflow based on flags.
    
    Args:
        row_data: CSV row data
        check_dedupe: Whether to check dedupe
        send_leads: Whether to create lead
    
    Returns:
        Normalized response dictionary
    """
    if check_dedupe and not send_leads:
        phone = row_data.get('phoneNumber') or row_data.get('phonenumber') or row_data.get('mobile')
        pan = row_data.get('pan')
        return check_creditsea_dedupe(phone, pan)
    
    if not check_dedupe and send_leads:
        return create_creditsea_lead(row_data)
    
    if check_dedupe and send_leads:
        phone = row_data.get('phoneNumber') or row_data.get('phonenumber') or row_data.get('mobile')
        pan = row_data.get('pan')
        dedupe_result = check_creditsea_dedupe(phone, pan)
        
        if dedupe_result.get("status") != "SUCCESS":
            return dedupe_result
        
        if dedupe_result.get("result") == "DUPLICATE":
            return {
                "status": "SUCCESS",
                "result": "DUPLICATE"
            }
        
        return create_creditsea_lead(row_data)
    
    return {
        "status": "FAILED",
        "result": "NO_ACTION_SELECTED"
    }
