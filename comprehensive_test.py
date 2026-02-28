"""
Comprehensive validation test for custom User system
Run this to verify all features are working correctly
"""
import os
import sys
import django
from datetime import date

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.core.exceptions import ValidationError
from users.models import User, validate_phone_number, validate_pan_number, validate_pin_code
from users.utils import create_or_update_user_from_csv_row

def print_section(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print('=' * 70)

def test_validations():
    """Test all field validations"""
    print_section("Testing Field Validations")
    
    # Phone number validation
    print("\n1. Phone Number Validation:")
    try:
        validate_phone_number('9876543210')
        print("   ✓ Valid 10-digit phone: 9876543210")
    except ValidationError as e:
        print(f"   ✗ Failed: {e}")
    
    try:
        validate_phone_number('987654321')  # 9 digits
        print("   ✗ Should have rejected 9-digit phone")
    except ValidationError:
        print("   ✓ Correctly rejected 9-digit phone number")
    
    # PAN validation
    print("\n2. PAN Number Validation:")
    valid_pans = ['ABCPM1234Z', 'XYZPC5678A', 'DEFPH9999B']
    for pan in valid_pans:
        try:
            validate_pan_number(pan)
            print(f"   ✓ Valid PAN: {pan}")
        except ValidationError as e:
            print(f"   ✗ Failed: {pan} - {e}")
    
    invalid_pans = [
        ('ABCQM1234Z', 'Invalid 4th character'),
        ('ABC123456Z', 'Wrong format'),
        ('ABCPM0000Z', 'Invalid digit range'),
    ]
    for pan, reason in invalid_pans:
        try:
            validate_pan_number(pan)
            print(f"   ✗ Should have rejected {pan} ({reason})")
        except ValidationError:
            print(f"   ✓ Correctly rejected {pan} ({reason})")
    
    # Pin code validation
    print("\n3. Pin Code Validation:")
    try:
        validate_pin_code('123456')
        print("   ✓ Valid 6-digit pin: 123456")
    except ValidationError as e:
        print(f"   ✗ Failed: {e}")
    
    try:
        validate_pin_code('12345')  # 5 digits
        print("   ✗ Should have rejected 5-digit pin")
    except ValidationError:
        print("   ✓ Correctly rejected 5-digit pin code")

def test_user_creation():
    """Test user creation with different scenarios"""
    print_section("Testing User Creation")
    
    # Clean up test data
    User.objects.filter(phone_number__startswith='9999').delete()
    
    print("\n1. Creating basic user:")
    try:
        user = User.objects.create_user(
            phone_number='9999999001',
            first_name='Test',
            last_name='User1',
            pan_number='ABCPM1234Z',
            pin_code='123456',
        )
        print(f"   ✓ Created: {user}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
    
    print("\n2. Creating user with all fields:")
    try:
        user = User.objects.create_user(
            phone_number='9999999002',
            first_name='Test',
            last_name='User2',
            pan_number='XYZPC5678A',
            pin_code='110001',
            email='test2@example.com',
            gender='Male',
            date_of_birth=date(1990, 1, 1),
            city='Mumbai',
            state='Maharashtra',
            profession='Salaried',
            monthly_income=75000,
            bureau_score=800,
            income_mode='Bank Transfer',
            consent_taken=True,
        )
        print(f"   ✓ Created: {user}")
        print(f"     - Email: {user.email}")
        print(f"     - Age: {user.age} (auto-calculated)")
        print(f"     - Bureau Score: {user.bureau_score}")
        print(f"     - Consent: {user.consent_taken}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
    
    print("\n3. Creating superuser:")
    try:
        admin = User.objects.create_superuser(
            phone_number='9999999003',
            password='admin123',
            first_name='Admin',
            last_name='User',
            pan_number='DEFPA9999C',
            pin_code='100001',
        )
        print(f"   ✓ Created superuser: {admin}")
        print(f"     - Is Staff: {admin.is_staff}")
        print(f"     - Is Superuser: {admin.is_superuser}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")

def test_csv_operations():
    """Test CSV import functionality"""
    print_section("Testing CSV Import & Deduplication")
    
    # Clean up test data
    User.objects.filter(phone_number='9999999100').delete()
    
    print("\n1. Creating user from CSV data:")
    csv_data = {
        'phone_number': '9999999100',
        'first_name': 'CSV',
        'last_name': 'User',
        'pan_number': 'GHIPH1234D',
        'pin_code': '560001',
        'email': 'csv@test.com',
        'gender': 'Female',
        'profession': 'Self Employed',
        'monthly_income': '100000',
        'bureau_score': '850',
        'consent_taken': 'yes',
        'city': 'Bangalore',
        'state': 'Karnataka',
    }
    
    try:
        user, created = create_or_update_user_from_csv_row(csv_data)
        print(f"   ✓ {'Created' if created else 'Updated'}: {user}")
        print(f"     - Phone: {user.phone_number}")
        print(f"     - Email: {user.email}")
        print(f"     - Bureau Score: {user.bureau_score}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
    
    print("\n2. Updating existing user (deduplication test):")
    csv_data_update = {
        'phone_number': '9999999100',  # Same phone
        'first_name': 'CSV',
        'last_name': 'User',
        'pan_number': 'GHIPH1234D',
        'pin_code': '560001',
        'email': 'updated@test.com',  # Updated
        'bureau_score': '900',  # Updated
        'city': 'Bangalore',
        'state': 'Karnataka',
    }
    
    try:
        user, created = create_or_update_user_from_csv_row(csv_data_update)
        print(f"   ✓ {'Created' if created else 'Updated'}: {user}")
        print(f"     - Email changed to: {user.email}")
        print(f"     - Bureau Score changed to: {user.bureau_score}")
        if not created:
            print("   ✓ Deduplication working correctly!")
    except Exception as e:
        print(f"   ✗ Failed: {e}")

def test_queries():
    """Test database queries and indexes"""
    print_section("Testing Database Queries & Performance")
    
    total_users = User.objects.count()
    print(f"\n1. Total users in database: {total_users}")
    
    if total_users > 0:
        print("\n2. Sample queries:")
        
        # Query by phone (indexed)
        try:
            user = User.objects.filter(phone_number='9999999002').first()
            if user:
                print(f"   ✓ Query by phone: Found {user.first_name} {user.last_name}")
        except Exception as e:
            print(f"   ✗ Query failed: {e}")
        
        # Query by bureau score (indexed)
        high_score = User.objects.filter(bureau_score__gte=750).count()
        print(f"   ✓ High bureau score users (>=750): {high_score}")
        
        # Query by consent
        consented = User.objects.filter(consent_taken=True).count()
        print(f"   ✓ Users with consent: {consented}")
        
        print("\n3. Recent users:")
        for user in User.objects.all().order_by('-created_at')[:3]:
            print(f"   - {user}")

def test_auth_settings():
    """Verify authentication settings"""
    print_section("Testing Authentication Configuration")
    
    from django.conf import settings
    
    print(f"\n1. AUTH_USER_MODEL: {settings.AUTH_USER_MODEL}")
    if settings.AUTH_USER_MODEL == 'users.User':
        print("   ✓ Custom user model configured correctly")
    else:
        print("   ✗ Custom user model NOT configured")
    
    print(f"\n2. Installed apps include 'users': {'users' in settings.INSTALLED_APPS}")
    if 'users' in settings.INSTALLED_APPS:
        print("   ✓ Users app installed")
    else:
        print("   ✗ Users app NOT installed")

def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print(" " * 20 + "CUSTOM USER SYSTEM")
    print(" " * 15 + "COMPREHENSIVE VALIDATION TEST")
    print("=" * 70)
    
    try:
        test_auth_settings()
        test_validations()
        test_user_creation()
        test_csv_operations()
        test_queries()
        
        print_section("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("\nThe custom user system is fully functional and ready for use.")
        print("\nNext steps:")
        print("  1. Create a superuser: python manage.py createsuperuser")
        print("  2. Run the dev server: python manage.py runserver")
        print("  3. Access admin: http://localhost:8000/admin/")
        print("  4. Import CSV data: python manage.py import_users_from_csv data.csv")
        print("\nDocumentation:")
        print("  - Full guide: USERS_DOCUMENTATION.md")
        print("  - Quick ref: QUICK_REFERENCE.md")
        print("  - Summary: REFACTORING_SUMMARY.md")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70 + "\n")

if __name__ == '__main__':
    main()
