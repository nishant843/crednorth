"""
Utility functions for user management, including CSV processing.
"""
from datetime import datetime
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import User


def create_or_update_user_from_csv_row(data_dict):
    """
    Helper function to create or update a user from CSV row data.
    Deduplicates by phone_number: if user exists, updates fields; otherwise creates new user.
    
    Args:
        data_dict (dict): Dictionary containing user data from CSV row.
                         Expected keys (case-insensitive):
                         - phone_number (required)
                         - country_code (optional, defaults to '91')
                         - email (optional)
                         - pan_number (required)
                         - first_name (required)
                         - last_name (required)
                         - gender (optional)
                         - date_of_birth or dob (optional, format: YYYY-MM-DD)
                         - city (optional)
                         - state (optional)
                         - pin_code (optional)
                         - profession (optional)
                         - monthly_income (optional)
                         - bureau_score (optional)
                         - income_mode (optional)
                         - consent_taken (optional, boolean)
    
    Returns:
        tuple: (user_instance, created_flag)
               - user_instance: The User object that was created or updated
               - created_flag: Boolean indicating if user was newly created (True) or updated (False)
    
    Raises:
        ValidationError: If required fields are missing or validation fails
        ValueError: If data types cannot be converted properly
    """
    
    # Normalize keys to lowercase for case-insensitive matching
    data = {k.lower().strip(): v for k, v in data_dict.items()}
    
    # Extract phone_number (required for deduplication)
    phone_number = data.get('phone_number', '').strip()
    if not phone_number:
        raise ValidationError('phone_number is required')
    
    # Clean phone_number - remove any non-digit characters
    phone_number = ''.join(filter(str.isdigit, phone_number))
    
    # Prepare user data
    user_data = {}
    
    # Contact information
    user_data['country_code'] = data.get('country_code', '91').strip()
    
    email = data.get('email', '').strip()
    user_data['email'] = email if email else None
    
    # Identity information
    pan_number = data.get('pan_number', data.get('pan', '')).strip().upper()
    if pan_number:
        user_data['pan_number'] = pan_number
    
    # Personal information
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    if not first_name or not last_name:
        raise ValidationError('first_name and last_name are required')
    
    user_data['first_name'] = first_name
    user_data['last_name'] = last_name
    
    # Gender
    gender = data.get('gender', '').strip()
    if gender:
        # Normalize gender values
        gender_map = {
            'm': 'Male',
            'male': 'Male',
            'f': 'Female',
            'female': 'Female',
            'o': 'Other',
            'other': 'Other',
        }
        user_data['gender'] = gender_map.get(gender.lower(), gender)
    
    # Date of birth
    dob = data.get('date_of_birth', data.get('dob', '')).strip()
    if dob:
        try:
            # Try to parse various date formats
            for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d'):
                try:
                    user_data['date_of_birth'] = datetime.strptime(dob, fmt).date()
                    break
                except ValueError:
                    continue
        except Exception:
            pass  # Skip if date parsing fails
    
    # Location information
    city = data.get('city', '').strip()
    if city:
        user_data['city'] = city
    
    state = data.get('state', '').strip()
    if state:
        user_data['state'] = state
    
    pin_code = data.get('pin_code', data.get('pincode', '')).strip()
    if pin_code:
        # Clean pin_code - keep only digits
        pin_code = ''.join(filter(str.isdigit, pin_code))
        user_data['pin_code'] = pin_code
    
    # Employment and financial information
    profession = data.get('profession', '').strip()
    if profession:
        # Normalize profession values to match PROFESSION_CHOICES
        profession_map = {
            'salaried': 'Salaried',
            'self employed': 'Self-Employed',
            'self_employed': 'Self-Employed',
            'self-employed': 'Self-Employed',
            'selfemployed': 'Self-Employed',
            'business': 'Business',
        }
        mapped = profession_map.get(profession.lower())
        # Only set profession if it's one of the valid choices
        if mapped and mapped in ['Salaried', 'Self-Employed', 'Business']:
            user_data['profession'] = mapped
        elif profession in ['Salaried', 'Self-Employed', 'Business']:
            user_data['profession'] = profession
    
    monthly_income = data.get('monthly_income', data.get('income', '')).strip()
    if monthly_income:
        try:
            # Remove any currency symbols and commas
            monthly_income = ''.join(filter(str.isdigit, str(monthly_income)))
            if monthly_income:
                user_data['monthly_income'] = int(monthly_income)
        except (ValueError, TypeError):
            pass  # Skip if conversion fails
    
    bureau_score = data.get('bureau_score', data.get('credit_score', '')).strip()
    if bureau_score:
        try:
            score = int(bureau_score)
            if 0 <= score <= 900:
                user_data['bureau_score'] = score
        except (ValueError, TypeError):
            pass  # Skip if conversion fails
    
    income_mode = data.get('income_mode', '').strip()
    if income_mode:
        # Normalize income_mode values
        income_mode_map = {
            'cheque': 'Cheque',
            'bank transfer': 'Bank Transfer',
            'bank_transfer': 'Bank Transfer',
            'banktransfer': 'Bank Transfer',
            'cash': 'Cash',
        }
        user_data['income_mode'] = income_mode_map.get(income_mode.lower(), income_mode)
    
    # Consent
    consent = data.get('consent_taken', data.get('consent', '')).strip()
    if consent:
        # Convert various boolean representations
        consent_true_values = ['true', 'yes', 'y', '1', 'true', 't']
        user_data['consent_taken'] = str(consent).lower() in consent_true_values
    
    # Use transaction to ensure atomicity
    with transaction.atomic():
        try:
            # Try to get existing user by phone_number
            user = User.objects.get(phone_number=phone_number)
            
            # Update existing user
            for field, value in user_data.items():
                setattr(user, field, value)
            
            user.save()
            created = False
            
        except User.DoesNotExist:
            # Create new user
            user_data['phone_number'] = phone_number
            user = User.objects.create_user(**user_data)
            created = True
    
    return user, created
