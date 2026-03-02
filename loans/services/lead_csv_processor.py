"""
Utility functions for processing Lead CSV uploads.
Leads are PRIMARY - CSV uploads create Leads → auto-generate Users.
Leads are potential customers with no lender associations.
"""
from datetime import datetime
from django.core.exceptions import ValidationError
from django.db import transaction
from users.models import User


def create_or_update_lead_from_csv_row(data_dict):
    """
    Helper function to create or update a Lead from CSV row data.
    Deduplicates by phone_number (globally unique).
    
    NOTE: Creating/updating a Lead automatically triggers User creation via signal.
    
    Args:
        data_dict (dict): Dictionary containing lead data from CSV row.
                         Expected keys (case-insensitive):
                         - phone_number (REQUIRED, 10 digits)
                         - first_name (optional)
                         - last_name (optional)
                         - pan_number (optional, format: AAAAA9999A)
                         - pin_code (optional, 6 digits)
                         - email (optional)
                         - date_of_birth or dob (optional, format: YYYY-MM-DD)
                         - gender (optional: Male/Female/Other)
                         - city, state (optional)
                         - profession (optional: Salaried/Self-Employed/Business)
                         - monthly_income (optional)
                         - bureau_score (optional, 0-900)
                         - consent_taken (optional, boolean)
                         - status (optional: pending/approved/rejected)
    
    Returns:
        tuple: (lead_instance, created_flag)
               - lead_instance: The Lead object that was created or updated
               - created_flag: Boolean indicating if lead was newly created (True) or updated (False)
    
    Raises:
        ValidationError: If required fields are missing or validation fails
        ValueError: If data types cannot be converted properly
    """
    
    # Normalize keys to lowercase for case-insensitive matching
    data = {k.lower().strip(): v for k, v in data_dict.items() if v}
    
    # Extract REQUIRED field - only phone_number
    phone_number = data.get('phone_number', '').strip()
    if not phone_number:
        raise ValidationError('phone_number is required')
    
    # Clean phone number - remove any non-digit characters
    phone_number = ''.join(filter(str.isdigit, phone_number))
    if len(phone_number) != 10:
        raise ValidationError(f'phone_number must be exactly 10 digits, got: {phone_number}')
    
    # Prepare lead data (only phone_number is required)
    lead_data = {
        'phone_number': phone_number,
    }
    
    # Extract optional fields
    first_name = data.get('first_name', '').strip()
    if first_name:
        lead_data['first_name'] = first_name
    
    last_name = data.get('last_name', '').strip()
    if last_name:
        lead_data['last_name'] = last_name
    
    pan_number = data.get('pan_number', data.get('pan', '')).strip().upper()
    if pan_number:
        lead_data['pan_number'] = pan_number
    
    pin_code = data.get('pin_code', data.get('pincode', '')).strip()
    if pin_code:
        if len(pin_code) != 6:
            pin_code = pin_code.zfill(6)  # Pad with zeros if needed
        lead_data['pin_code'] = pin_code
    
    # Email
    email = data.get('email', '').strip()
    if email:
        lead_data['email'] = email
    
    # Gender
    gender = data.get('gender', '').strip()
    if gender:
        gender_map = {
            'm': 'Male',
            'male': 'Male',
            'f': 'Female',
            'female': 'Female',
            'o': 'Other',
            'other': 'Other',
        }
        lead_data['gender'] = gender_map.get(gender.lower(), gender)
    
    # Date of birth
    dob = data.get('date_of_birth', data.get('dob', '')).strip()
    if dob:
        try:
            for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d'):
                try:
                    lead_data['date_of_birth'] = datetime.strptime(dob, fmt).date()
                    break
                except ValueError:
                    continue
        except:
            pass  # Skip if date parsing fails
    
    # Location
    if 'city' in data:
        lead_data['city'] = data['city'].strip()
    if 'state' in data:
        lead_data['state'] = data['state'].strip()
    
    # Profession
    profession = data.get('profession', data.get('employment_type', '')).strip()
    if profession:
        prof_map = {
            'salaried': 'Salaried',
            'self employed': 'Self-Employed',
            'self-employed': 'Self-Employed',
            'business': 'Business',
        }
        # Only accept valid profession values
        mapped_profession = prof_map.get(profession.lower())
        if mapped_profession:
            lead_data['profession'] = mapped_profession
        elif profession in ['Salaried', 'Self-Employed', 'Business']:
            lead_data['profession'] = profession
    
    # Monthly income
    income = data.get('monthly_income', data.get('income', '')).strip()
    if income:
        try:
            lead_data['monthly_income'] = float(income)
        except ValueError:
            pass
    
    # Bureau score
    bureau_score = data.get('bureau_score', '').strip()
    if bureau_score:
        try:
            score = int(bureau_score)
            if 0 <= score <= 900:
                lead_data['bureau_score'] = score
        except ValueError:
            pass
    
    # Consent
    consent = data.get('consent_taken', data.get('consent', '')).strip().lower()
    if consent in ('true', '1', 'yes', 'y'):
        lead_data['consent_taken'] = True
    elif consent in ('false', '0', 'no', 'n'):
        lead_data['consent_taken'] = False
    
    # Status
    status = data.get('status', '').strip().lower()
    if status in ('pending', 'approved', 'rejected'):
        lead_data['status'] = status
    
    # Deduplicate by phone_number (globally unique now)
    # Previously: dedupe was by phone + lender, but now leads can exist without lender
    try:
        lead = User.objects.get(phone_number=phone_number)
        # Update existing lead
        for key, value in lead_data.items():
            if key != 'phone_number':  # Don't update primary identifier
                setattr(lead, key, value)
        lead.save()
        return lead, False  # Updated
    except User.DoesNotExist:
        # Create new lead
        lead = User.objects.create(**lead_data)
        return lead, True  # Created


def bulk_create_or_update_leads_from_csv(csv_data):
    """
    Process a list of CSV rows and create/update Leads in bulk.
    Each Lead creation automatically triggers User creation via signal.
    
    Args:
        csv_data: List of dictionaries (from csv.DictReader)
    
    Returns:
        dict: {
            'created': int,  # Number of leads created
            'updated': int,  # Number of leads updated
            'failed': int,   # Number of rows that failed
            'errors': list   # List of error messages
        }
    """
    created = 0
    updated = 0
    failed = 0
    errors = []
    
    for row_num, row_data in enumerate(csv_data, start=2):  # Start at 2 (header is row 1)
        try:
            with transaction.atomic():
                lead, was_created = create_or_update_lead_from_csv_row(row_data)
                if was_created:
                    created += 1
                else:
                    updated += 1
        except ValidationError as e:
            failed += 1
            errors.append(f"Row {row_num}: {str(e)}")
        except Exception as e:
            failed += 1
            errors.append(f"Row {row_num}: {str(e)}")
    
    return {
        'created': created,
        'updated': updated,
        'failed': failed,
        'errors': errors
    }
