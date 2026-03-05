"""
Script to populate database with 100 dummy leads and associated users.
Run with: python populate_100_leads.py
"""

import os
import django
import random
from datetime import date, timedelta
from decimal import Decimal

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from users.models import User
from users.models import User

# Data pools for generating realistic dummy data
FIRST_NAMES = [
    'Amit', 'Priya', 'Rahul', 'Sneha', 'Vikas', 'Neha', 'Arjun', 'Pooja', 'Ravi', 'Anita',
    'Suresh', 'Kavita', 'Arun', 'Divya', 'Manoj', 'Shweta', 'Vikram', 'Rani', 'Karan', 'Meera',
    'Sanjay', 'Deepika', 'Ajay', 'Nisha', 'Ramesh', 'Suman', 'Vijay', 'Rekha', 'Anil', 'Geeta',
    'Prakash', 'Swati', 'Rajesh', 'Preeti', 'Ashok', 'Manju', 'Sachin', 'Anjali', 'Naveen', 'Shalini',
    'Rohan', 'Megha', 'Abhishek', 'Ritu', 'Gaurav', 'Jyoti', 'Nitesh', 'Priyanka', 'Sandeep', 'Aarti'
]

LAST_NAMES = [
    'Sharma', 'Kumar', 'Singh', 'Patel', 'Gupta', 'Verma', 'Reddy', 'Shah', 'Joshi', 'Nair',
    'Mehta', 'Rao', 'Iyer', 'Malhotra', 'Agarwal', 'Jain', 'Tiwari', 'Sinha', 'Mishra', 'Pandey',
    'Saxena', 'Kapoor', 'Bhatia', 'Chopra', 'Arora', 'Bansal', 'Kulkarni', 'Deshmukh', 'Pillai', 'Menon'
]

CITIES = [
    'Mumbai', 'Delhi', 'Bangalore', 'Hyderabad', 'Chennai', 'Kolkata', 'Pune', 'Ahmedabad',
    'Jaipur', 'Lucknow', 'Chandigarh', 'Indore', 'Nagpur', 'Coimbatore', 'Kochi', 'Visakhapatnam',
    'Surat', 'Vadodara', 'Bhopal', 'Ludhiana'
]

STATES = [
    'Maharashtra', 'Delhi', 'Karnataka', 'Telangana', 'Tamil Nadu', 'West Bengal', 'Gujarat',
    'Rajasthan', 'Uttar Pradesh', 'Punjab', 'Madhya Pradesh', 'Kerala', 'Andhra Pradesh',
    'Haryana', 'Bihar', 'Odisha'
]

PROFESSIONS = ['Salaried', 'Self Employed', 'Student']
GENDERS = ['Male', 'Female', 'Other']
STATUSES = ['pending', 'approved', 'rejected']
INCOME_MODES = ['Cheque', 'Bank Transfer', 'Cash']

# PAN number components
PAN_PREFIXES = ['ABCDE', 'FGHIJ', 'KLMNO', 'PQRST', 'UVWXY']
PAN_TYPES = ['P', 'C', 'H', 'F', 'A', 'T', 'B', 'G', 'J', 'L']


def generate_phone_number(index):
    """Generate unique phone number"""
    base = 9000000000 + index
    return str(base)


def generate_pan_number():
    """Generate valid PAN number"""
    prefix = random.choice(PAN_PREFIXES)
    pan_type = random.choice(PAN_TYPES)
    number = random.randint(1000, 9999)
    suffix = random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    return f"{prefix[0:3]}{pan_type}{prefix[4]}{number}{suffix}"


def generate_pin_code():
    """Generate valid 6-digit pin code"""
    return str(random.randint(100000, 999999))


def generate_dob():
    """Generate date of birth (age between 21 and 65)"""
    today = date.today()
    years_ago = random.randint(21, 65)
    days_offset = random.randint(0, 365)
    return today - timedelta(days=years_ago * 365 + days_offset)


def main():
    print("=" * 60)
    print("POPULATING DATABASE WITH 100 DUMMY LEADS")
    print("=" * 60)
    
    created_count = 0
    skipped_count = 0
    
    for i in range(1, 101):
        phone_number = generate_phone_number(i)
        
        # Check if user already exists
        if User.objects.filter(phone_number=phone_number).exists():
            print(f"[{i}/100] Skipped - User with phone {phone_number} already exists")
            skipped_count += 1
            continue
        
        try:
            # Create User (passwordless - no password field)
            user = User.objects.create_user(
                phone_number=phone_number
            )
            
            # Generate lead data
            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)
            gender = random.choice(GENDERS)
            dob = generate_dob()
            city = random.choice(CITIES)
            state = random.choice(STATES)
            pin_code = generate_pin_code()
            profession = random.choice(PROFESSIONS)
            monthly_income = Decimal(random.randint(20000, 150000))
            bureau_score = random.randint(550, 850)
            status = random.choice(STATUSES)
            income_mode = random.choice(INCOME_MODES)
            consent_taken = random.choice([True, False])
            email = f"{first_name.lower()}.{last_name.lower()}{i}@example.com"
            pan_number = generate_pan_number()
            
            # Create Lead
            lead = User.objects.create(
                user=user,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                email=email,
                pan_number=pan_number,
                date_of_birth=dob,
                gender=gender,
                city=city,
                state=state,
                pin_code=pin_code,
                profession=profession,
                monthly_income=monthly_income,
                bureau_score=bureau_score,
                income_mode=income_mode,
                status=status,
                consent_taken=consent_taken
            )
            
            created_count += 1
            print(f"[{i}/100] ✓ Created: {first_name} {last_name} | Phone: {phone_number} | Bureau: {bureau_score}")
            
        except Exception as e:
            print(f"[{i}/100] ✗ Error: {e}")
            skipped_count += 1
    
    print("\n" + "=" * 60)
    print(f"SUMMARY")
    print("=" * 60)
    print(f"✓ Successfully created: {created_count} leads")
    print(f"⊗ Skipped: {skipped_count} leads")
    print(f"Total Users in DB: {User.objects.count()}")
    print(f"Total Leads in DB: {User.objects.count()}")
    print("=" * 60)


if __name__ == '__main__':
    main()
