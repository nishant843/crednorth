"""
Quick test script for custom user system
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from users.models import User
from users.utils import create_or_update_user_from_csv_row

def test_csv_import():
    """Test CSV import functionality"""
    print("Testing CSV import functionality...")
    
    csv_data = {
        'phone_number': '9123456789',
        'first_name': 'CSV',
        'last_name': 'Test',
        'pan_number': 'ABCPA1234B',
        'email': 'csv@test.com',
        'pin_code': '110001',
        'gender': 'Male',
        'profession': 'Salaried',
        'monthly_income': '75000',
        'bureau_score': '800',
        'consent_taken': 'yes',
        'city': 'Delhi',
        'state': 'Delhi',
    }
    
    user, created = create_or_update_user_from_csv_row(csv_data)
    
    status = "Created" if created else "Updated"
    print(f"✓ {status} user: {user.phone_number} - {user.first_name} {user.last_name}")
    print(f"  Email: {user.email}")
    print(f"  Bureau Score: {user.bureau_score}")
    print(f"  Consent: {user.consent_taken}")
    
    # Test update
    print("\nTesting update of existing user...")
    csv_data['email'] = 'updated@test.com'
    csv_data['bureau_score'] = '850'
    
    user, created = create_or_update_user_from_csv_row(csv_data)
    status = "Created" if created else "Updated"
    print(f"✓ {status} user: {user.phone_number}")
    print(f"  New Email: {user.email}")
    print(f"  New Bureau Score: {user.bureau_score}")

def test_user_count():
    """Display current user count"""
    count = User.objects.count()
    print(f"\nTotal users in database: {count}")
    
    if count > 0:
        print("\nLast 3 users:")
        for user in User.objects.all()[:3]:
            print(f"  - {user}")

if __name__ == '__main__':
    print("=" * 60)
    print("Custom User System Test")
    print("=" * 60)
    print()
    
    test_csv_import()
    test_user_count()
    
    print()
    print("=" * 60)
    print("All tests completed successfully! ✓")
    print("=" * 60)
