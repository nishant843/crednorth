from django.test import TestCase
from django.core.exceptions import ValidationError
from .models import User, validate_phone_number, validate_pan_number, validate_pin_code
from .utils import create_or_update_user_from_csv_row
from datetime import date


class UserModelTest(TestCase):
    """Test cases for User model"""
    
    def setUp(self):
        """Set up test data"""
        self.user_data = {
            'phone_number': '9876543210',
            'first_name': 'John',
            'last_name': 'Doe',
            'pan_number': 'ABCPM1234Z',
            'pin_code': '123456',
        }
    
    def test_create_user(self):
        """Test user creation"""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.phone_number, '9876543210')
        self.assertEqual(user.first_name, 'John')
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
    
    def test_create_superuser(self):
        """Test superuser creation"""
        user = User.objects.create_superuser(
            phone_number='9999999999',
            password='testpass123',
            first_name='Admin',
            last_name='User',
            pan_number='ABCPP1234Z',
            pin_code='123456',
        )
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
    
    def test_phone_number_validation(self):
        """Test phone number validation"""
        # Valid phone number
        validate_phone_number('9876543210')
        
        # Invalid: not 10 digits
        with self.assertRaises(ValidationError):
            validate_phone_number('987654321')
        
        # Invalid: contains non-digits
        with self.assertRaises(ValidationError):
            validate_phone_number('98765a4321')
    
    def test_pan_validation(self):
        """Test PAN number validation"""
        # Valid PAN
        validate_pan_number('ABCPM1234Z')
        validate_pan_number('XYZPC5678A')
        
        # Invalid: wrong format
        with self.assertRaises(ValidationError):
            validate_pan_number('ABC1234567')
        
        # Invalid: wrong fourth character
        with self.assertRaises(ValidationError):
            validate_pan_number('ABCQM1234Z')
        
        # Invalid: digits out of range
        with self.assertRaises(ValidationError):
            validate_pan_number('ABCPM0000Z')
    
    def test_pin_code_validation(self):
        """Test pin code validation"""
        # Valid pin code
        validate_pin_code('123456')
        
        # Invalid: not 6 digits
        with self.assertRaises(ValidationError):
            validate_pin_code('12345')
        
        # Invalid: contains non-digits
        with self.assertRaises(ValidationError):
            validate_pin_code('12345a')
    
    def test_age_calculation(self):
        """Test automatic age calculation"""
        user = User.objects.create_user(
            phone_number='9876543210',
            first_name='John',
            last_name='Doe',
            pan_number='ABCPM1234Z',
            pin_code='123456',
            date_of_birth=date(1990, 1, 1),
        )
        self.assertIsNotNone(user.age)
        self.assertTrue(user.age > 30)
    
    def test_user_str(self):
        """Test string representation"""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(str(user), 'John Doe (9876543210)')


class CSVUtilsTest(TestCase):
    """Test cases for CSV utility functions"""
    
    def test_create_user_from_csv(self):
        """Test creating user from CSV data"""
        csv_data = {
            'phone_number': '9876543210',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'pan_number': 'XYZPA1234B',
            'email': 'jane@example.com',
            'pin_code': '123456',
        }
        user, created = create_or_update_user_from_csv_row(csv_data)
        self.assertTrue(created)
        self.assertEqual(user.phone_number, '9876543210')
        self.assertEqual(user.email, 'jane@example.com')
    
    def test_update_user_from_csv(self):
        """Test updating existing user from CSV data"""
        # Create initial user
        User.objects.create_user(
            phone_number='9876543210',
            first_name='Jane',
            last_name='Smith',
            pan_number='XYZPA1234B',
            pin_code='123456',
        )
        
        # Update via CSV
        csv_data = {
            'phone_number': '9876543210',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'pan_number': 'XYZPA1234B',
            'email': 'newemail@example.com',
            'city': 'Mumbai',
            'pin_code': '123456',
        }
        user, created = create_or_update_user_from_csv_row(csv_data)
        self.assertFalse(created)
        self.assertEqual(user.email, 'newemail@example.com')
        self.assertEqual(user.city, 'Mumbai')
