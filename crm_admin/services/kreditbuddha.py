"""
KreditBuddha integration service.
Handles pushing leads to KreditBuddha API.
Dedupe is internal to their API.
"""

import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

def push_lead(payload: dict) -> dict:
    """
    Push a single lead to KreditBuddha API.
    
    Returns:
        dict: {
            'success': bool,
            'message': str,
            'data': dict (if success),
            'status': int (1 for success, 2 for error)
        }
    """
    cfg = getattr(settings, 'KREDITBUDDHA', {}) or {}
    base_url = cfg.get('BASE_URL', 'https://api.kreditfinpro.com')
    auth_key = cfg.get('AUTH_KEY')
    username = cfg.get('USERNAME')
    proxy_url = cfg.get('PROXY_URL')

    if not all([base_url, auth_key, username]):
        return {
            'success': False,
            'message': 'Missing KREDITBUDDHA configuration (base_url, AUTH_KEY, USERNAME)'
        }

    url = f"{base_url.rstrip('/')}/marketing-push-lead-data"

    headers = {
        'Auth': auth_key,
        'Username': username,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else None

    try:
        response = requests.post(url, json=payload, headers=headers, proxies=proxies, timeout=15)
        
        try:
            data = response.json()
        except Exception as exc:
            return {
                'success': False,
                'message': f'Invalid JSON response from KreditBuddha: {exc}'
            }
            
        status = data.get('status')
        if status is None:
            status = data.get('Status')
        error = data.get('error') or data.get('Error')
        message = data.get('message') or data.get('Message') or ''

        if status == 1:
            return {
                'success': True,
                'message': message,
                'data': data
            }

        # Any non-1 status is a failure. Besides the documented status=2 (Error),
        # KreditBuddha also returns status=0 for validation failures (e.g. missing
        # mandatory fields), putting the human-readable reason in "message" rather
        # than "error" -- surface whichever is populated instead of a generic message.
        return {
            'success': False,
            'message': error or message or f'Unexpected response from KreditBuddha (status={status})'
        }
            
    except requests.exceptions.Timeout as exc:
        return {
            'success': False,
            'message': f'KreditBuddha lead push timeout: {exc}'
        }
    except requests.exceptions.HTTPError as exc:
        return {
            'success': False,
            'message': f'KreditBuddha lead push HTTP error: {exc}'
        }
    except requests.exceptions.RequestException as exc:
        return {
            'success': False,
            'message': f'KreditBuddha lead push request error: {exc}'
        }
    except Exception as exc:
        return {
            'success': False,
            'message': f'KreditBuddha lead push unexpected error: {exc}'
        }
