"""
LendingPlate integration service.
LendingPlate performs dedupe internally, so only lead push is required.
"""

import json
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

    mobile_raw = str(lead_data.get('mobile', '')).strip()
    pincode_raw = str(lead_data.get('pincode', '')).strip()
    monthly_income_value = str(lead_data.get('net_mothlyincome', '')).strip().replace(',', '')

    # Handle CSV/Excel artifacts like trailing .0 and non-digit separators.
    mobile = ''.join(ch for ch in mobile_raw if ch.isdigit())
    pincode = ''.join(ch for ch in pincode_raw if ch.isdigit())

    monthly_income_raw = monthly_income_value
    if monthly_income_value.endswith('.0'):
        monthly_income_raw = monthly_income_value[:-2]

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

    profession_raw = str(lead_data.get('profession', '')).strip().lower()
    profession = 'SAL'
    if profession_raw:
        profession = 'SAL' if profession_raw in ('sal', 'salaried', 'salary') else 'SEP'

    payload = {
        'partner_id': config['PARTNER_ID'],
        'ref_id': _normalize_ref_id(lead_data.get('ref_id')),
        'mobile': mobile,
        'customer_name': str(lead_data.get('customer_name', '')).strip()[:50],
        'pancard': str(lead_data.get('pancard', '')).strip().upper(),
        'dob': dob_value,
        'pincode': pincode,
        'profession': profession,
        'net_mothlyincome': str(monthly_income),
    }

    url = f"{config['BASE_URL']}/api/v2/partner/generate_lead"

    token = config['API_TOKEN']
    token_lower = token.lower()
    if token_lower.startswith('bearer '):
        raw_token = token.split(' ', 1)[1].strip()
        candidate_tokens = [token, raw_token]
    else:
        candidate_tokens = [token, f'Bearer {token}']
    candidate_tokens = [t for t in dict.fromkeys(candidate_tokens) if t]

    def _extract_json_response(response_obj):
        try:
            return response_obj.json(), None
        except ValueError:
            response_text = response_obj.text or ''
            json_start = response_text.find('{')
            json_end = response_text.rfind('}')
            if json_start != -1 and json_end > json_start:
                try:
                    return json.loads(response_text[json_start:json_end + 1]), None
                except (ValueError, TypeError) as exc:
                    return None, f'Invalid JSON response from LendingPlate: {exc}'
            return None, 'Invalid JSON response from LendingPlate: JSON object not found in body'

    def _is_token_or_method_error(message_text):
        text = str(message_text or '').strip().lower()
        return (
            'invalid token' in text
            or 'request method' in text
            or 'unauthorized' in text
            or 'method not allowed' in text
        )

    last_failure = {
        'success': False,
        'message': 'LendingPlate lead push failed after trying auth variants',
        'data': {},
    }

    for auth_value in candidate_tokens:
        headers = {
            'Authorization': auth_value,
            'Content-Type': 'application/json',
        }

        try:
            response = SESSION.post(url, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()

            data, parse_error = _extract_json_response(response)
            if parse_error:
                last_failure = {
                    'success': False,
                    'message': parse_error,
                    'data': {},
                }
                continue

            status_value = str(data.get('status') or data.get('Status') or '').strip().lower()
            message = str(data.get('message') or data.get('Message') or '').strip() or 'Unknown response from LendingPlate'

            if status_value in ('s', 'success'):
                return {
                    'success': True,
                    'message': message,
                    'data': data,
                }

            if status_value in ('fail', 'f', 'error'):
                last_failure = {
                    'success': False,
                    'message': message,
                    'data': data,
                }
                if _is_token_or_method_error(message):
                    continue
                return last_failure

            last_failure = {
                'success': False,
                'message': f'Unexpected LendingPlate response status: {data.get("status") or data.get("Status")}',
                'data': data,
            }
            return last_failure

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
            last_failure = {
                'success': False,
                'message': f'LendingPlate lead push HTTP error: {exc} body={body}',
                'data': {},
            }
            if _is_token_or_method_error(body) or (exc.response is not None and exc.response.status_code in (401, 403, 405)):
                continue
            return last_failure
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

    return last_failure
