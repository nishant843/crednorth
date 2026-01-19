"""
CreditSea lead creation module.
Handles lead push for a single CSV row to CreditSea API.
"""

import os
import requests


def push_lead_to_creditsea(lead_data: dict) -> dict:
    """
    Push a single lead to CreditSea API.
    
    Args:
        lead_data: Dictionary containing lead information from CSV row
    
    Returns:
        Dictionary with normalized response:
        - {"status": "SUCCESS", "result": "LEAD_CREATED", "lead_id": "...", "utm_link": "..."} - Success
        - {"status": "FAILED", "result": "VALIDATION_ERROR", "message": "..."} - Missing field
        - {"status": "FAILED", "result": "API_REJECTED", "message": "..."} - API returned error
        - {"status": "FAILED", "result": "API_ERROR", "message": "..."} - Network error
    """
    # Validate required fields
    required_fields = [
        'firstname', 'lastname', 'phonenumber', 'pan', 
        'dob', 'gender', 'pincode', 'income', 'employmenttype'
    ]
    
    for field in required_fields:
        value = lead_data.get(field)
        if value is None or str(value).strip() == '':
            return {
                "status": "FAILED",
                "result": "VALIDATION_ERROR",
                "message": f"Missing field: {field}"
            }
    
    # Get source ID from environment
    source_id = os.environ.get("CREDITSEA_SOURCE_ID")
    if not source_id:
        return {
            "status": "FAILED",
            "result": "API_ERROR",
            "message": "Missing CREDITSEA_SOURCE_ID"
        }
    
    # Build request payload
    payload = {
        "firstName": str(lead_data['firstname']).strip(),
        "lastName": str(lead_data['lastname']).strip(),
        "phoneNumber": str(lead_data['phonenumber']).strip(),
        "pan": str(lead_data['pan']).strip(),
        "dob": str(lead_data['dob']).strip(),
        "gender": str(lead_data['gender']).strip(),
        "pincode": str(lead_data['pincode']).strip(),
        "income": int(lead_data['income']),
        "employmentType": str(lead_data['employmenttype']).strip()
    }
    
    headers = {
        "Content-Type": "application/json",
        "sourceid": source_id
    }
    
    url = "https://creditsea.com/api/v1/lead/create"
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        response.raise_for_status()
        
        data = response.json()
        
        # Parse success response
        if data.get("message") == "Lead generated successfully":
            return {
                "status": "SUCCESS",
                "result": "LEAD_CREATED",
                "lead_id": str(data.get("leadId", "")),
                "utm_link": str(data.get("utmLink", ""))
            }
        
        # API returned unexpected success format
        return {
            "status": "FAILED",
            "result": "API_REJECTED",
            "message": data.get("message", "Unknown error")
        }
        
    except requests.exceptions.HTTPError as e:
        # API reachable but returned error status
        try:
            error_data = e.response.json()
            message = error_data.get("message", str(e))
        except:
            message = str(e)
        
        return {
            "status": "FAILED",
            "result": "API_REJECTED",
            "message": message
        }
    
    except (requests.exceptions.RequestException, ValueError) as e:
        # Network error, timeout, or JSON parse error
        return {
            "status": "FAILED",
            "result": "API_ERROR",
            "message": str(e)
        }
    
    except Exception as e:
        # Unexpected error
        return {
            "status": "FAILED",
            "result": "API_ERROR",
            "message": str(e)
        }
