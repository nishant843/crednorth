"""
LendingPlate integration service.
LendingPlate performs dedupe internally, so only lead push is required.
"""

import random
from datetime import datetime

import requests
from django.conf import settings


SESSION = requests.Session()
TIMEOUT_SECONDS = 15


def _get_config():
    cfg = getattr(settings, 'LENDINGPLATE', {}) or {}

    environment = str(cfg.get('ENV', 'production')).strip().lower()
    if environment == 'uat':
        base_url = str(cfg.get('UAT_BASE_URL', '')).rstrip('/')
    else:
        base_url = str(cfg.get('PRODUCTION_BASE_URL', '')).rstrip('/')

    partner_id = str(cfg.get('PARTNER_ID', '')).strip()
    api_token = str(cfg.get('API_TOKEN', '')).strip()

    if not base_url or not partner_id or not api_token:
        raise ValueError(
            'Missing LENDINGPLATE configuration (base URL, PARTNER_ID, API_TOKEN)'
        )

    return {
        'BASE_URL': base_url,
        'PARTNER_ID': partner_id,
        'API_TOKEN': api_token,
    }


def _to_ddmmyyyy(dob_value):
    raw = str(dob_value or '').strip()
    if not raw:
        return ''

    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(raw, fmt).strftime('%d/%m/%Y')
        except ValueError:
            continue

    return raw


def _normalize_ref_id(raw_value):
    raw = ''.join(ch for ch in str(raw_value or '') if ch.isdigit())
    if 5 <= len(raw) <= 10:
        return raw
    if len(raw) > 10:
        return raw[:10]
    return str(random.randint(10000, 9999999999))


def push_lead(lead_data: dict) -> dict:
    """
    Push a single lead to LendingPlate lead origination API.
    """
    config = _get_config()
    url = f"{config['BASE_URL']}/api/v2/partner/generate_lead"

    mobile = str(lead_data.get('mobile', '')).strip()
    pincode = str(lead_data.get('pincode', '')).strip()
    monthly_income_raw = str(lead_data.get('net_mothlyincome', '')).strip().replace(',', '')

    if len(mobile) != 10 or not mobile.isdigit():
        return {
            'success': False,
            'message': 'Invalid mobile format. Expected 10 digit number.',
            'data': {}
        }

    if len(pincode) != 6 or not pincode.isdigit():
        return {
            'success': False,
            'message': 'Invalid pincode format. Expected 6 digit number.',
            'data': {}
        }

    if not monthly_income_raw.isdigit():
        return {
            'success': False,
            'message': 'Invalid monthly income format. Expected numeric value.',
            'data': {}
        }

    monthly_income = int(monthly_income_raw)
    if monthly_income < 1 or monthly_income > 1000000:
        return {
            'success': False,
            'message': 'Monthly income out of range. Expected between 1 and 1000000.',
            'data': {}
        }

    dob_value = _to_ddmmyyyy(lead_data.get('dob'))
    if dob_value:
        try:
            datetime.strptime(dob_value, '%d/%m/%Y')
        except ValueError:
            return {
                'success': False,
                'message': 'Invalid dob format. Expected DD/MM/YYYY.',
                'data': {}
            }

    payload = {
        'partner_id': config['PARTNER_ID'],
        'ref_id': _normalize_ref_id(lead_data.get('ref_id')),
        'mobile': mobile,
        'customer_name': str(lead_data.get('customer_name', '')).strip()[:50],
        'pancard': str(lead_data.get('pancard', '')).strip().upper(),
        'dob': dob_value,
        'pincode': pincode,
        'profession': 'SAL',
        'net_mothlyincome': str(monthly_income),
    }

    headers = {
        'Authorization': f"Bearer {config['API_TOKEN']}",
        'Content-Type': 'application/json',
    }

    try:
        response = SESSION.post(url, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()

        try:
            data = response.json()
        except ValueError as exc:
            return {
                'success': False,
                'message': f'Invalid JSON response from LendingPlate: {exc}',
                'data': {},
            }

        status_value = str(data.get('status', '')).strip().lower()
        message = str(data.get('message', '')).strip() or 'Unknown response from LendingPlate'

        if status_value == 's':
            return {
                'success': True,
                'message': message,
                'data': data,
            }

        if status_value in ('fail', 'error'):
            return {
                'success': False,
                'message': message,
                'data': data,
            }

        return {
            'success': False,
            'message': f'Unexpected LendingPlate response status: {data.get("status")}',
            'data': data,
        }

    except requests.exceptions.Timeout as exc:
        return {
            'success': False,
            'message': f'LendingPlate lead push timeout: {exc}',
            'data': {},
        }
    except requests.exceptions.HTTPError as exc:
        body = ''
        if exc.response is not None:
            body = exc.response.text[:500]
        return {
            'success': False,
            'message': f'LendingPlate lead push HTTP error: {exc} body={body}',
            'data': {},
        }
    except requests.exceptions.RequestException as exc:
        return {
            'success': False,
            'message': f'LendingPlate lead push request error: {exc}',
            'data': {},
        }
    except Exception as exc:
        return {
            'success': False,
            'message': f'LendingPlate lead push unexpected error: {exc}',
            'data': {},
        }
