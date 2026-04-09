"""
Lender API call module for dedupe checking.
Handles individual user checks against specific lenders.
"""

from typing import Optional
from .creditsea_dedupe import check_creditsea_dedupe
from .creditsea_lead import create_creditsea_lead
from crm_admin.services.tezcredit import check_dedupe as check_tezcredit_dedupe
from crm_admin.services.tezcredit import push_lead as push_tezcredit_lead
from crm_admin.services.lendingplate import push_lead as push_lendingplate_lead


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

    if lender_lower == "tezcredit":
        return _process_tezcredit(row_data, check_dedupe, send_leads)

    if lender_lower == "lendingplate":
        return _process_lendingplate(row_data, check_dedupe, send_leads)
    
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


def _process_tezcredit(row_data: dict, check_dedupe: bool, send_leads: bool) -> dict:
    """
    Process TezCredit workflow based on flags.

    Follows the same response shape and control flow as CreditSea processing.
    """
    mobile = (
        row_data.get('mobile')
        or row_data.get('phoneNumber')
        or row_data.get('phonenumber')
        or row_data.get('phone_number')
    )

    if mobile is None or str(mobile).strip() == '':
        return {
            "status": "FAILED",
            "result": "VALIDATION_ERROR",
            "message": "Missing field: mobile"
        }

    customer_name = ' '.join(
        part for part in [
            str(row_data.get('first_name', '')).strip(),
            str(row_data.get('last_name', '')).strip(),
        ] if part
    ).strip()
    if not customer_name:
        customer_name = str(row_data.get('name', '')).strip()

    lead_payload = {
        'ref_id': row_data.get('ref_id') or row_data.get('reference_id') or row_data.get('id'),
        'mobile': str(mobile).strip(),
        'customer_name': customer_name,
        'pancard': row_data.get('pan') or row_data.get('pan_number') or row_data.get('pancard') or '',
        'dob': row_data.get('dob') or row_data.get('date_of_birth') or '',
        'pincode': row_data.get('pinCode') or row_data.get('pincode') or row_data.get('pin_code') or '',
        'net_mothlyincome': row_data.get('income') or row_data.get('monthly_income') or '',
    }

    if check_dedupe and not send_leads:
        try:
            is_duplicate = check_tezcredit_dedupe(lead_payload['mobile'])
        except Exception as exc:
            return {
                "status": "FAILED",
                "result": "API_ERROR",
                "message": str(exc)
            }

        return {
            "status": "SUCCESS",
            "result": "DUPLICATE" if is_duplicate else "NOT_DUPLICATE"
        }

    if not check_dedupe and send_leads:
        push_result = push_tezcredit_lead(lead_payload)
        if push_result.get('success'):
            return {
                "status": "SUCCESS",
                "result": "LEAD_CREATED",
                "lead_id": str((push_result.get('data') or {}).get('lead_id', '')),
                "utm_link": str((push_result.get('data') or {}).get('utm_link', '')),
                "message": push_result.get('message', '')
            }

        return {
            "status": "FAILED",
            "result": "API_REJECTED",
            "message": push_result.get('message', 'TezCredit lead push failed')
        }

    if check_dedupe and send_leads:
        try:
            is_duplicate = check_tezcredit_dedupe(lead_payload['mobile'])
        except Exception as exc:
            return {
                "status": "FAILED",
                "result": "API_ERROR",
                "message": str(exc)
            }

        if is_duplicate:
            return {
                "status": "SUCCESS",
                "result": "DUPLICATE"
            }

        push_result = push_tezcredit_lead(lead_payload)
        if push_result.get('success'):
            return {
                "status": "SUCCESS",
                "result": "LEAD_CREATED",
                "lead_id": str((push_result.get('data') or {}).get('lead_id', '')),
                "utm_link": str((push_result.get('data') or {}).get('utm_link', '')),
                "message": push_result.get('message', '')
            }

        return {
            "status": "FAILED",
            "result": "API_REJECTED",
            "message": push_result.get('message', 'TezCredit lead push failed')
        }

    return {
        "status": "FAILED",
        "result": "NO_ACTION_SELECTED"
    }


def _process_lendingplate(row_data: dict, check_dedupe: bool, send_leads: bool) -> dict:
    """
    Process LendingPlate workflow.

    LendingPlate performs dedupe internally, so this flow is push-only.
    """
    mobile = (
        row_data.get('mobile')
        or row_data.get('phoneNumber')
        or row_data.get('phonenumber')
        or row_data.get('phone_number')
    )

    pincode = (
        row_data.get('pinCode')
        or row_data.get('pincode')
        or row_data.get('pin_code')
    )

    customer_name = ' '.join(
        part for part in [
            str(row_data.get('first_name', '')).strip(),
            str(row_data.get('last_name', '')).strip(),
        ] if part
    ).strip()
    if not customer_name:
        customer_name = str(row_data.get('name', '')).strip()

    lead_payload = {
        'ref_id': row_data.get('ref_id') or row_data.get('reference_id') or row_data.get('id'),
        'mobile': str(mobile or '').strip(),
        'customer_name': customer_name,
        'pancard': row_data.get('pan') or row_data.get('pan_number') or row_data.get('pancard') or '',
        'dob': row_data.get('dob') or row_data.get('date_of_birth') or '',
        'pincode': str(pincode or '').strip(),
        'net_mothlyincome': (
            row_data.get('net_mothlyincome')
            or row_data.get('net_monthly_income')
            or row_data.get('monthly_income')
            or row_data.get('monthly income')
            or row_data.get('income')
            or ''
        ),
        'profession': row_data.get('profession') or '',
    }

    push_result = push_lendingplate_lead(lead_payload)
    error_message = str(push_result.get('message', 'LendingPlate lead push failed'))
    is_duplicate_message = any(
        marker in error_message.lower()
        for marker in ('existing user', 'already exists', 'duplicate')
    )

    if check_dedupe and not send_leads:
        if push_result.get('success'):
            return {
                "status": "SUCCESS",
                "result": "NOT_DUPLICATE",
                "message": push_result.get('message', '')
            }

        if is_duplicate_message:
            return {
                "status": "SUCCESS",
                "result": "DUPLICATE",
                "message": error_message
            }

        is_technical_error = any(
            marker in error_message.lower()
            for marker in ('timeout', 'http error', 'request error', 'unexpected error', 'invalid json')
        )
        return {
            "status": "FAILED",
            "result": "API_ERROR" if is_technical_error else "API_REJECTED",
            "message": error_message
        }

    if push_result.get('success'):
        return {
            "status": "SUCCESS",
            "result": "LEAD_CREATED",
            "lead_id": str((push_result.get('data') or {}).get('ref_id', '')),
            "utm_link": '',
            "message": push_result.get('message', '')
        }

    if is_duplicate_message:
        return {
            "status": "SUCCESS",
            "result": "DUPLICATE",
            "message": error_message
        }

    is_technical_error = any(
        marker in error_message.lower()
        for marker in ('timeout', 'http error', 'request error', 'unexpected error', 'invalid json')
    )

    is_validation_error = any(
        marker in error_message.lower()
        for marker in (
            'invalid mobile format',
            'invalid pincode format',
            'invalid monthly income format',
            'monthly income out of range',
            'invalid dob format',
        )
    )

    return {
        "status": "FAILED",
        "result": "API_ERROR" if is_technical_error else ("VALIDATION_ERROR" if is_validation_error else "API_REJECTED"),
        "message": error_message
    }
