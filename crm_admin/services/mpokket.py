"""
Mpokket integration service.

Unlike KreditBuddha/BrightLoans/LendingPlate, Mpokket exposes a separate
dedupe-check API and a separate lead-push API (same shape as TezCredit).
Production only -- Mpokket whitelists a fixed outbound IP, so calls are
routed through the same proxy used by KreditBuddha/BrightLoans.
"""

import base64
import logging
from datetime import datetime

import requests
from django.conf import settings

logger = logging.getLogger(__name__)
SESSION = requests.Session()
TIMEOUT_SECONDS = 15


def _get_config():
    cfg = getattr(settings, 'MPOKKET', {}) or {}
    base_url = str(cfg.get('BASE_URL', '')).rstrip('/')
    api_key = cfg.get('API_KEY')
    proxy_url = cfg.get('PROXY_URL')

    if not base_url or not api_key:
        raise ValueError('Missing MPOKKET configuration (BASE_URL, API_KEY)')

    return {
        'BASE_URL': base_url,
        'API_KEY': api_key,
        'PROXIES': {'http': proxy_url, 'https': proxy_url} if proxy_url else None,
    }


def _b64(value) -> str:
    return base64.b64encode(str(value or '').strip().encode()).decode()


def _to_ddmmyyyy(value):
    raw = str(value or '').strip()
    if not raw:
        return ''

    for fmt in ('%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(raw, fmt).strftime('%d-%m-%Y')
        except ValueError:
            continue

    return raw


_DEDUPE_OUTCOMES = {
    '1205': 'NEW',
    '1206': 'ELIGIBLE',
    '1207': 'NOT_ELIGIBLE',
    '1208': 'REJECTED',
}


def check_dedupe(email: str, mobile: str) -> dict:
    """
    Check dedupe with Mpokket.

    Returns:
        {'outcome': 'NEW'|'ELIGIBLE'|'NOT_ELIGIBLE'|'REJECTED',
         'message': str,
         'borrow_limit': str (only for ELIGIBLE)}

    Raises:
        RuntimeError for API/network/invalid response errors.
    """
    config = _get_config()
    url = f"{config['BASE_URL']}/acquisition-affiliate/v1/dedupe/check"
    headers = {
        'api-key': config['API_KEY'],
        'Content-Type': 'application/json',
    }
    payload = {
        'email_id': _b64(email),
        'mobile_number': _b64(mobile),
    }

    try:
        response = SESSION.post(
            url, json=payload, headers=headers, proxies=config['PROXIES'], timeout=TIMEOUT_SECONDS
        )

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f'Invalid JSON response from Mpokket dedupe: {exc}')

        if not data.get('success'):
            errors = data.get('error_message') or [data.get('message') or 'Unknown error']
            if isinstance(errors, str):
                errors = [errors]
            raise RuntimeError(f"Mpokket dedupe rejected request: {'; '.join(str(e) for e in errors)}")

        status_code = str(data.get('statusCode') or data.get('status_code') or '').strip()
        outcome = _DEDUPE_OUTCOMES.get(status_code)
        if outcome is None:
            raise RuntimeError(f'Unexpected Mpokket dedupe response (statusCode={status_code!r}): {data!r}')

        result = {
            'outcome': outcome,
            'message': data.get('message', ''),
        }
        if outcome == 'ELIGIBLE':
            result['borrow_limit'] = (data.get('data') or {}).get('borrow_limit')

        return result

    except requests.exceptions.Timeout as exc:
        raise RuntimeError(f'Mpokket dedupe timeout: {exc}')
    except requests.exceptions.HTTPError as exc:
        body = ''
        if exc.response is not None:
            body = exc.response.text[:500]
        raise RuntimeError(f'Mpokket dedupe HTTP error: {exc} body={body}')
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f'Mpokket dedupe request error: {exc}')


def push_lead(payload: dict) -> dict:
    """
    Push a single lead to Mpokket.

    Returns:
        dict: {'success': bool, 'message': str, 'data': dict}
    """
    config = _get_config()
    url = f"{config['BASE_URL']}/acquisition-affiliate/v1/user"
    headers = {
        'api-key': config['API_KEY'],
        'Content-Type': 'application/json',
    }

    try:
        response = SESSION.post(
            url, json=payload, headers=headers, proxies=config['PROXIES'], timeout=TIMEOUT_SECONDS
        )

        try:
            data = response.json()
        except ValueError as exc:
            return {
                'success': False,
                'message': f'Invalid JSON response from Mpokket: {exc}',
                'data': {},
            }

        # Success responses carry a string message; failure responses carry a
        # list (e.g. ["Invalid mobile_no"]) -- normalize to a string either way.
        raw_message = data.get('message', '')
        message = '; '.join(str(m) for m in raw_message) if isinstance(raw_message, list) else str(raw_message)

        if data.get('success'):
            return {
                'success': True,
                'message': message,
                'data': data.get('data') or {},
            }

        return {
            'success': False,
            'message': message or f"Unexpected response from Mpokket (status_code={data.get('status_code')})",
            'data': {},
        }

    except requests.exceptions.Timeout as exc:
        return {
            'success': False,
            'message': f'Mpokket lead push timeout: {exc}',
            'data': {},
        }
    except requests.exceptions.HTTPError as exc:
        body = ''
        if exc.response is not None:
            body = exc.response.text[:500]
        return {
            'success': False,
            'message': f'Mpokket lead push HTTP error: {exc} body={body}',
            'data': {},
        }
    except requests.exceptions.RequestException as exc:
        return {
            'success': False,
            'message': f'Mpokket lead push request error: {exc}',
            'data': {},
        }
    except Exception as exc:
        return {
            'success': False,
            'message': f'Mpokket lead push unexpected error: {exc}',
            'data': {},
        }
