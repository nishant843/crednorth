"""
CreditSea lead creation module.
"""

import requests


CREDITSEA_SOURCE_ID = "85674567"


def create_creditsea_lead(row_data: dict) -> dict:
    """
    Create a lead in CreditSea API.
    
    Args:
        row_data: Dictionary containing lead information from CSV row
    
    Returns:
        Dictionary with normalized response:
        - {"status": "SUCCESS", "result": "LEAD_CREATED", "lead_id": "...", "utm_link": "..."} - Success
        - {"status": "FAILED", "result": "VALIDATION_ERROR", "message": "..."} - Missing field
        - {"status": "FAILED", "result": "API_REJECTED", "message": "..."} - API returned error
        - {"status": "FAILED", "result": "API_ERROR"} - Network error
    """
    required_fields = [
        'first_name', 'last_name', 'phoneNumber', 'pan', 
        'dob', 'gender', 'pinCode', 'income', 'employmentType'
    ]
    
    for field in required_fields:
        value = row_data.get(field)
        if value is None or str(value).strip() == '':
            return {
                "status": "FAILED",
                "result": "VALIDATION_ERROR",
                "message": f"Missing field: {field}"
            }
    
    payload = {
        "first_name": str(row_data['first_name']).strip(),
        "last_name": str(row_data['last_name']).strip(),
        "phoneNumber": str(row_data['phoneNumber']).strip(),
        "pan": str(row_data['pan']).strip(),
        "dob": str(row_data['dob']).strip(),
        "gender": str(row_data['gender']).strip().lower(),
        "pinCode": str(row_data['pinCode']).strip(),
        "income": str(row_data['income']).strip(),
        "employmentType": str(row_data['employmentType']).strip().lower()
    }
    
    headers = {
        "Content-Type": "application/json",
        "sourceid": CREDITSEA_SOURCE_ID
    }
    
    url = "https://backend.creditsea.com/api/v1/leads/create-lead-dsa"
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("message") == "Lead generated successfully":
            return {
                "status": "SUCCESS",
                "result": "LEAD_CREATED",
                "lead_id": str(data.get("leadId", "")),
                "utm_link": str(data.get("utmLink", ""))
            }
        
        return {
            "status": "FAILED",
            "result": "API_REJECTED",
            "message": data.get("message", "Unknown error")
        }
        
    except requests.exceptions.HTTPError as e:
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
    
    except Exception as e:
        return {
            "status": "FAILED",
            "result": "API_ERROR",
            "message": str(e)
        }
