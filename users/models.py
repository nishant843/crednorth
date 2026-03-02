from django.db import models
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from datetime import date
import re
from .managers import UserManager


def calculate_age_from_dob(dob):
    """
    Calculate age from date of birth.
    Returns None if dob is None.
    """
    if not dob:
        return None
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return age


def validate_phone_number(value):
    """
    Validate that phone number is exactly 10 digits.
    """
    if not value:
        raise ValidationError('Phone number is required.')
    if not value.isdigit():
        raise ValidationError('Phone number must contain only digits.')
    if len(value) != 10:
        raise ValidationError('Phone number must be exactly 10 digits.')


def validate_pan_number(value):
    """
    Validate PAN number format:
    - Exactly 10 characters
    - First 5: Uppercase letters
    - Next 4: Digits from 0001 to 9999
    - Last 1: Uppercase letter
    - Fourth letter must be one of: P, C, H, F, A, T, B, G, J, L
    """
    if not value:
        return  # Allow null/blank if field allows it
    
    if len(value) != 10:
        raise ValidationError('PAN must be exactly 10 characters.')
    
    # Check pattern: 5 letters + 4 digits + 1 letter
    pan_pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
    if not re.match(pan_pattern, value):
        raise ValidationError(
            'PAN must have format: 5 uppercase letters, 4 digits, 1 uppercase letter.'
        )
    
    # Fourth character validation
    valid_fourth_chars = ['P', 'C', 'H', 'F', 'A', 'T', 'B', 'G', 'J', 'L']
    if value[3] not in valid_fourth_chars:
        raise ValidationError(
            f'Fourth character must be one of: {", ".join(valid_fourth_chars)}.'
        )
    
    # Validate digit range (0001 to 9999)
    digit_part = value[5:9]
    digit_value = int(digit_part)
    if digit_value < 1 or digit_value > 9999:
        raise ValidationError('PAN digits must be between 0001 and 9999.')


def validate_pin_code(value):
    """
    Validate that pin code is exactly 6 digits.
    """
    if not value:
        return
    if not value.isdigit():
        raise ValidationError('Pin code must contain only digits.')
    if len(value) != 6:
        raise ValidationError('Pin code must be exactly 6 digits.')


class User(PermissionsMixin, models.Model):
    """
    Unified User model - A user IS a lead.
    Contains all authentication and profile information in a single table.
    Uses phone_number as the unique identifier.
    No password field - authentication will be via OTP in the future.
    Only phone_number is required, all other fields are optional.
    """
    
    # Status choices
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]

    PROFESSION_CHOICES = [
        ('Salaried', 'Salaried'),
        ('Self-Employed', 'Self-Employed'),
        ('Business', 'Business'),
    ]

    INCOME_MODE_CHOICES = [
        ('Cheque', 'Cheque'),
        ('Bank Transfer', 'Bank Transfer'),
        ('Cash', 'Cash'),
    ]
    
    # Primary key - BigAutoField for scalability
    id = models.BigAutoField(primary_key=True)
    
    # Phone number (REQUIRED - used for login and unique identifier)
    phone_number = models.CharField(
        max_length=10,
        unique=True,
        validators=[validate_phone_number],
        db_index=True,
        help_text='Exactly 10 digits - used for login'
    )
    
    # Personal Information (ALL OPTIONAL)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(max_length=254, null=True, blank=True)
    pan_number = models.CharField(
        max_length=10,
        db_index=True,
        validators=[validate_pan_number],
        help_text='PAN format: AAAAA9999A',
        blank=True
    )
    date_of_birth = models.DateField(null=True, blank=True)
    age = models.IntegerField(null=True, blank=True, editable=False)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    
    # Location (ALL OPTIONAL)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pin_code = models.CharField(
        max_length=6,
        validators=[validate_pin_code],
        help_text='6 digits',
        blank=True
    )
    
    # Financial Information (ALL OPTIONAL)
    profession = models.CharField(max_length=100, choices=PROFESSION_CHOICES, blank=True)
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    bureau_score = models.IntegerField(null=True, blank=True, db_index=True, help_text='Credit score 0-900')
    income_mode = models.CharField(max_length=20, choices=INCOME_MODE_CHOICES, blank=True)
    
    # Consent
    consent_taken = models.BooleanField(default=False)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Django auth fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Custom manager
    objects = UserManager()
    
    # Define phone_number as the username field for authentication
    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []
    
    # Required methods for Django auth backend
    @property
    def is_anonymous(self):
        return False
    
    @property
    def is_authenticated(self):
        return True
    
    def get_username(self):
        return self.phone_number
    
    def natural_key(self):
        return (self.phone_number,)
    
    @property
    def calculated_age(self):
        """
        Property to get real-time calculated age from date_of_birth.
        This ensures age is always current even if not saved recently.
        """
        return calculate_age_from_dob(self.date_of_birth)
    
    class Meta:
        db_table = 'users_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number'], name='idx_user_phone'),
            models.Index(fields=['pan_number'], name='idx_user_pan'),
            models.Index(fields=['status'], name='idx_user_status'),
            models.Index(fields=['bureau_score'], name='idx_user_bureau'),
            models.Index(fields=['created_at'], name='idx_user_created_at'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['pan_number'],
                name='unique_user_pan_number',
                condition=models.Q(pan_number__isnull=False) & ~models.Q(pan_number='')
            ),
        ]
    
    def __str__(self):
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name} - {self.phone_number} ({self.status})"
        return f"User {self.phone_number} ({self.status})"
    
    def clean(self):
        """
        Model-level validation.
        """
        super().clean()
        
        # Validate phone number
        validate_phone_number(self.phone_number)
        
        # Validate PAN if provided
        if self.pan_number:
            validate_pan_number(self.pan_number)
        
        # Validate pin code if provided
        if self.pin_code:
            validate_pin_code(self.pin_code)
    
    def save(self, *args, **kwargs):
        """
        Override save to run validation and calculate age.
        """
        # Calculate age from date_of_birth before saving
        if self.date_of_birth:
            self.age = calculate_age_from_dob(self.date_of_birth)
        else:
            self.age = None
        
        # Run full clean validation
        self.full_clean()
        
        super().save(*args, **kwargs)
