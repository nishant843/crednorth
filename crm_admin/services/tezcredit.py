"""
TezCredit integration service.
Follows the same service style used by CreditSea integrations.
"""

import logging
from datetime import datetime
from uuid import uuid4

import requests
from django.conf import settings


logger = logging.getLogger(__name__)
SESSION = requests.Session()
TIMEOUT_SECONDS = 10


def _get_config():
    cfg = getattr(settings, 'TEZCREDIT', {}) or {}
    dedupe_base_url = str(cfg.get('DEDUPE_BASE_URL', '')).rstrip('/')
    lms_base_url = str(cfg.get('LMS_BASE_URL', '')).rstrip('/')
    partner_id = str(cfg.get('PARTNER_ID', '')).strip()
    api_token = str(cfg.get('API_TOKEN') or '').strip()

    if not dedupe_base_url or not lms_base_url or not partner_id or not api_token:
        raise ValueError(
            'Missing TEZCREDIT configuration (DEDUPE_BASE_URL, LMS_BASE_URL, PARTNER_ID, API_TOKEN)'
        )

    return {
        'DEDUPE_BASE_URL': dedupe_base_url,
        'LMS_BASE_URL': lms_base_url,
        'PARTNER_ID': partner_id,
        'API_TOKEN': api_token,
    }


def _get_dedupe_config():
    cfg = getattr(settings, 'TEZCREDIT', {}) or {}
    dedupe_base_url = str(cfg.get('DEDUPE_BASE_URL', '')).rstrip('/')

    if not dedupe_base_url:
        raise ValueError('Missing TEZCREDIT configuration (DEDUPE_BASE_URL)')

    return {
        'DEDUPE_BASE_URL': dedupe_base_url,
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


def check_dedupe(mobile: str) -> bool:
    """
    Check dedupe with TezCredit.

    Returns:
        True if duplicate exists, False if safe to proceed.

    Raises:
        RuntimeError for API/network/invalid response errors.
    """
    config = _get_dedupe_config()
    url = f"{config['DEDUPE_BASE_URL']}/identity/dedupe/partnerDedupe"
    payload = {'mobile': str(mobile or '').strip()}

    try:
        response = SESSION.post(url, json=payload, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f'Invalid JSON response from TezCredit dedupe: {exc}')

        # Documented response shape:
        # {
        #   "statusCode": 200,
        #   "message": "Dedupe Check Successful",
        #   "data": { "found": true/false, "mobile": "..." }
        # }
        response_data = data.get('data') or {}

        duplicate_value = response_data.get('found')
        if isinstance(duplicate_value, bool):
            return duplicate_value

        # Backward-compatible fallbacks for alternate vendor payloads.
        for source in (response_data, data):
            for key in ('duplicate', 'is_duplicate', 'dedupe', 'exists', 'found'):
                if key not in source:
                    continue

                value = source.get(key)
                if isinstance(value, bool):
                    return value

                if isinstance(value, str):
                    normalized = value.strip().lower()
                    if normalized in ('true', '1', 'yes'):
                        return True
                    if normalized in ('false', '0', 'no'):
                        return False

                if value is not None:
                    return bool(value)

        raise RuntimeError('TezCredit dedupe response missing found/duplicate indicator')
    except requests.exceptions.Timeout as exc:
        logger.warning('TezCredit dedupe timeout for mobile=%s', payload['mobile'])
        raise RuntimeError(f'TezCredit dedupe timeout: {exc}')
    except requests.exceptions.HTTPError as exc:
        body = ''
        if exc.response is not None:
            body = exc.response.text[:500]
        raise RuntimeError(f'TezCredit dedupe HTTP error: {exc} body={body}')
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f'TezCredit dedupe request error: {exc}')


def push_lead(lead_data: dict) -> dict:
    """
    Push a lead to TezCredit.

    Returns:
        {
            "success": True/False,
            "message": "...",
            "data": response_json_or_empty_dict
        }
    """
    config = _get_config()
    url = f"{config['LMS_BASE_URL']}/partner/generate_lead"

    mobile = str(lead_data.get('mobile', '')).strip()
    customer_name = str(lead_data.get('customer_name', '')).strip()

    payload = {
        'partner_id': config['PARTNER_ID'],
        'ref_id': str(lead_data.get('ref_id') or uuid4()),
        'mobile': mobile,
        'customer_name': customer_name,
        'pancard': str(lead_data.get('pancard', '')).strip(),
        'dob': _to_ddmmyyyy(lead_data.get('dob')),
        'pincode': str(lead_data.get('pincode', '')).strip(),
        'profession': 'SAL',
        'net_mothlyincome': lead_data.get('net_mothlyincome', ''),
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
                'message': f'Invalid JSON response from TezCredit lead API: {exc}',
                'data': {},
            }

        return {
            'success': True,
            'message': data.get('message', 'Lead pushed successfully'),
            'data': data,
        }

    except requests.exceptions.Timeout as exc:
        return {
            'success': False,
            'message': f'TezCredit lead push timeout: {exc}',
            'data': {},
        }
    except requests.exceptions.HTTPError as exc:
        body = ''
        if exc.response is not None:
            body = exc.response.text[:500]
        return {
            'success': False,
            'message': f'TezCredit lead push HTTP error: {exc} body={body}',
            'data': {},
        }
    except requests.exceptions.RequestException as exc:
        return {
            'success': False,
            'message': f'TezCredit lead push request error: {exc}',
            'data': {},
        }
    except Exception as exc:
        return {
            'success': False,
            'message': f'TezCredit lead push unexpected error: {exc}',
            'data': {},
        }
