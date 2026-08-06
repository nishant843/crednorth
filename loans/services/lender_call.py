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
from crm_admin.services.kreditbuddha import push_lead as push_kreditbuddha_lead
from crm_admin.services.brightloans import push_lead as push_brightloans_lead
from crm_admin.services.mpokket import check_dedupe as check_mpokket_dedupe
from crm_admin.services.mpokket import push_lead as push_mpokket_lead
from crm_admin.services.mpokket import _to_ddmmyyyy as _mpokket_to_ddmmyyyy


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
        
    if lender_lower == "kreditbuddha":
        return _process_kreditbuddha(row_data, check_dedupe, send_leads)

    if lender_lower == "brightloans":
        return _process_brightloans(row_data, check_dedupe, send_leads)

    if lender_lower == "mpokket":
        return _process_mpokket(row_data, check_dedupe, send_leads)

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


def _to_int(value):
    """Coerce a raw CSV value to int, stripping commas. Returns None if not numeric."""
    try:
        return int(str(value).strip().replace(',', ''))
    except (TypeError, ValueError):
        return None


def _process_kreditbuddha(row_data: dict, check_dedupe: bool, send_leads: bool) -> dict:
    """
    Process KreditBuddha workflow.

    KreditBuddha performs dedupe internally, so this flow is push-only.
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

    income_type = _to_int(row_data.get('income_type'))
    gender = 1 if str(row_data.get('gender', '')).lower() in ['male', 'm'] else 2

    lead_payload = {
        'full_name': customer_name,
        'mobile': str(mobile or '').strip(),
        'email': row_data.get('email') or '',
        'pancard': row_data.get('pan') or row_data.get('pan_number') or row_data.get('pancard') or '',
        'pincode': _to_int(pincode),
        'monthly_salary': _to_int(
            row_data.get('net_mothlyincome')
            or row_data.get('net_monthly_income')
            or row_data.get('monthly_income')
            or row_data.get('monthly income')
            or row_data.get('income')
        ),
        'income_type': income_type,
        'dob': row_data.get('dob') or row_data.get('date_of_birth') or '',
        'gender': gender,
        'next_salary_date': row_data.get('next_salary_date') or '',
        'company_name': row_data.get('company_name') or 'Kredit Buddha'
    }

    push_result = push_kreditbuddha_lead(lead_payload)
    error_message = str(push_result.get('message', 'KreditBuddha lead push failed'))
    is_duplicate_message = 'customer already exist' in error_message.lower()

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
            "lead_id": '',
            "utm_link": (push_result.get('data') or {}).get('apply_url') or '',
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


def _process_brightloans(row_data: dict, check_dedupe: bool, send_leads: bool) -> dict:
    """
    Process Brightloans workflow.

    Brightloans performs dedupe internally, so this flow is push-only.
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

    income_type = _to_int(row_data.get('income_type'))
    gender = 1 if str(row_data.get('gender', '')).lower() in ['male', 'm'] else 2

    lead_payload = {
        'full_name': customer_name,
        'mobile': str(mobile or '').strip(),
        'email': row_data.get('email') or '',
        'pancard': row_data.get('pan') or row_data.get('pan_number') or row_data.get('pancard') or '',
        'pincode': _to_int(pincode),
        'monthly_salary': _to_int(
            row_data.get('net_mothlyincome')
            or row_data.get('net_monthly_income')
            or row_data.get('monthly_income')
            or row_data.get('monthly income')
            or row_data.get('income')
        ),
        'income_type': income_type,
        'dob': row_data.get('dob') or row_data.get('date_of_birth') or '',
        'gender': gender,
        'next_salary_date': row_data.get('next_salary_date') or '',
        'company_name': row_data.get('company_name') or 'Brightloans'
    }

    push_result = push_brightloans_lead(lead_payload)
    error_message = str(push_result.get('message', 'Brightloans lead push failed'))
    is_duplicate_message = 'customer already exist' in error_message.lower()

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
            "lead_id": '',
            "utm_link": (push_result.get('data') or {}).get('apply_url') or '',
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


_MPOKKET_ADDITIONAL_INFO_FIELDS = [
    'loan_amount', 'loan_tenure', 'company_type', 'industry_type', 'company_name',
    'current_designation', 'company_address', 'company_pincode', 'company_city',
    'company_state', 'current_company_working_years', 'net_monthly_income',
    'salary_mode', 'bank_name', 'pancard', 'enter_fname_as_per_pancard',
    'enter_lname_as_per_pancard', 'current_address', 'current_pincode',
    'current_city', 'current_state', 'current_residence_type',
    'years_stayed_in_current_address', 'education_qualification', 'marital_status',
    'father_name', 'mother_name', 'current_total_emi_paid_per_month',
    'active_creditcard_holder', 'offical_email_id', 'college_name',
    'college_pincode', 'college_city', 'college_state', 'college_strength',
    'degree_type', 'degree_name', 'degree_specialisation',
    'degree_attendance_type', 'degree_start_date', 'degree_end_date',
]


def _normalize_mpokket_profession(raw):
    """Map free-text profession values to Mpokket's exact enum."""
    normalized = str(raw or '').strip().lower()
    if normalized == 'student':
        return 'Student'
    if normalized in ('salaried', 'sal', 'salary'):
        return 'Salaried'
    if normalized in ('prime sib', 'sib', 'self employed', 'self-employed', 'selfemployed'):
        return 'Prime SIB'
    return None


def _mpokket_dedupe_result(outcome_data: dict) -> dict:
    outcome = outcome_data['outcome']
    if outcome == 'NEW':
        return {"status": "SUCCESS", "result": "NOT_DUPLICATE"}
    if outcome == 'ELIGIBLE':
        return {
            "status": "SUCCESS",
            "result": "DUPLICATE_ELIGIBLE",
            "message": f"Existing lead, eligible (borrow_limit={outcome_data.get('borrow_limit')})"
        }
    if outcome == 'NOT_ELIGIBLE':
        return {"status": "SUCCESS", "result": "DUPLICATE_NOT_ELIGIBLE"}
    return {"status": "SUCCESS", "result": "DUPLICATE_REJECTED"}


def _process_mpokket(row_data: dict, check_dedupe: bool, send_leads: bool) -> dict:
    """
    Process Mpokket workflow.

    Mpokket exposes separate dedupe-check and lead-push APIs (unlike the
    internal-dedupe lenders), so this mirrors TezCredit's three-way branch.
    """
    mobile = (
        row_data.get('mobile')
        or row_data.get('phoneNumber')
        or row_data.get('phonenumber')
        or row_data.get('phone_number')
    )
    email = row_data.get('email') or row_data.get('email_id') or ''

    if mobile is None or str(mobile).strip() == '':
        return {
            "status": "FAILED",
            "result": "VALIDATION_ERROR",
            "message": "Missing field: mobile"
        }

    profession = _normalize_mpokket_profession(row_data.get('profession'))
    if profession is None:
        return {
            "status": "FAILED",
            "result": "VALIDATION_ERROR",
            "message": "Missing or unrecognized field: profession (expected Student/Salaried/Prime SIB)"
        }

    first_name = str(row_data.get('first_name', '')).strip()
    last_name = str(row_data.get('last_name', '')).strip()
    full_name = ' '.join(part for part in [first_name, last_name] if part).strip()
    if not full_name:
        full_name = str(row_data.get('name', '')).strip()

    additional_info = {
        field: str(row_data.get(field, '') or '').strip()
        for field in _MPOKKET_ADDITIONAL_INFO_FIELDS
    }

    lead_payload = {
        'email_id': str(email).strip(),
        'mobile_no': str(mobile).strip(),
        'full_name': full_name,
        'first_name': first_name,
        'last_name': last_name,
        'date_of_birth': _mpokket_to_ddmmyyyy(row_data.get('dob') or row_data.get('date_of_birth')),
        'gender': str(row_data.get('gender', '') or '').strip(),
        'profession': profession,
        'additional_info': additional_info,
    }

    def _do_push():
        push_result = push_mpokket_lead(lead_payload)
        if push_result.get('success'):
            return {
                "status": "SUCCESS",
                "result": "LEAD_CREATED",
                "lead_id": str((push_result.get('data') or {}).get('request_id', '')),
                "message": push_result.get('message', '')
            }
        return {
            "status": "FAILED",
            "result": "API_REJECTED",
            "message": push_result.get('message', 'Mpokket lead push failed')
        }

    if check_dedupe and not send_leads:
        try:
            outcome_data = check_mpokket_dedupe(email, mobile)
        except Exception as exc:
            return {
                "status": "FAILED",
                "result": "API_ERROR",
                "message": str(exc)
            }
        return _mpokket_dedupe_result(outcome_data)

    if not check_dedupe and send_leads:
        return _do_push()

    if check_dedupe and send_leads:
        try:
            outcome_data = check_mpokket_dedupe(email, mobile)
        except Exception as exc:
            return {
                "status": "FAILED",
                "result": "API_ERROR",
                "message": str(exc)
            }

        if outcome_data['outcome'] != 'NEW':
            return _mpokket_dedupe_result(outcome_data)

        return _do_push()

    return {
        "status": "FAILED",
        "result": "NO_ACTION_SELECTED"
    }
