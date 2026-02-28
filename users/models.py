import re
from datetime import date
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from .managers import UserManager


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


def calculate_age(dob):
    """
    Calculate age from date of birth.
    """
    if not dob:
        return None
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return age


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for CRM lead-level data.
    Designed to scale to millions of rows with proper indexing.
    Uses phone_number as the unique identifier instead of username.
    """
    
    # Gender choices
    GENDER_MALE = 'Male'
    GENDER_FEMALE = 'Female'
    GENDER_OTHER = 'Other'
    GENDER_CHOICES = [
        (GENDER_MALE, 'Male'),
        (GENDER_FEMALE, 'Female'),
        (GENDER_OTHER, 'Other'),
    ]
    
    # Profession choices
    PROFESSION_SALARIED = 'Salaried'
    PROFESSION_SELF_EMPLOYED = 'Self Employed'
    PROFESSION_STUDENT = 'Student'
    PROFESSION_CHOICES = [
        (PROFESSION_SALARIED, 'Salaried'),
        (PROFESSION_SELF_EMPLOYED, 'Self Employed'),
        (PROFESSION_STUDENT, 'Student'),
    ]
    
    # Income mode choices
    INCOME_MODE_CHEQUE = 'Cheque'
    INCOME_MODE_BANK_TRANSFER = 'Bank Transfer'
    INCOME_MODE_CASH = 'Cash'
    INCOME_MODE_CHOICES = [
        (INCOME_MODE_CHEQUE, 'Cheque'),
        (INCOME_MODE_BANK_TRANSFER, 'Bank Transfer'),
        (INCOME_MODE_CASH, 'Cash'),
    ]
    
    # Primary key - BigAutoField for scalability
    id = models.BigAutoField(primary_key=True)
    
    # Contact information
    country_code = models.CharField(
        max_length=5,
        default='91',
        help_text='Country calling code'
    )
    phone_number = models.CharField(
        max_length=10,
        unique=True,
        validators=[validate_phone_number],
        db_index=True,
        help_text='Exactly 10 digits'
    )
    email = models.EmailField(
        max_length=254,
        null=True,
        blank=True,
        help_text='Email address (optional)'
    )
    
    # Identity information
    pan_number = models.CharField(
        max_length=10,
        validators=[validate_pan_number],
        db_index=True,
        help_text='PAN format: 5 letters + 4 digits (0001-9999) + 1 letter'
    )
    
    # Personal information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        blank=True
    )
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        help_text='Date of birth'
    )
    age = models.IntegerField(
        null=True,
        blank=True,
        editable=False,
        help_text='Automatically calculated from date of birth'
    )
    
    # Location information
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pin_code = models.CharField(
        max_length=6,
        validators=[validate_pin_code],
        db_index=True,
        help_text='Exactly 6 digits'
    )
    
    # Employment and financial information
    profession = models.CharField(
        max_length=20,
        choices=PROFESSION_CHOICES,
        blank=True
    )
    monthly_income = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Monthly income in currency units'
    )
    bureau_score = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(900)],
        db_index=True,
        help_text='Credit bureau score (0-900)'
    )
    income_mode = models.CharField(
        max_length=20,
        choices=INCOME_MODE_CHOICES,
        blank=True
    )
    
    # Consent and permissions
    consent_taken = models.BooleanField(
        default=False,
        help_text='Whether user consent has been obtained'
    )
    
    # Django auth fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Custom manager
    objects = UserManager()
    
    # Define phone_number as the username field
    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'pan_number', 'pin_code']
    
    class Meta:
        db_table = 'users_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number'], name='idx_phone'),
            models.Index(fields=['pan_number'], name='idx_pan'),
            models.Index(fields=['pin_code'], name='idx_pincode'),
            models.Index(fields=['bureau_score'], name='idx_bureau_score'),
            models.Index(fields=['created_at'], name='idx_created_at'),
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.phone_number})"
    
    def clean(self):
        """
        Model-level validation for all fields.
        """
        super().clean()
        
        # Validate phone number
        validate_phone_number(self.phone_number)
        
        # Validate PAN number
        if self.pan_number:
            validate_pan_number(self.pan_number)
        
        # Validate pin code
        if self.pin_code:
            validate_pin_code(self.pin_code)
        
        # Validate bureau score range
        if self.bureau_score is not None:
            if self.bureau_score < 0 or self.bureau_score > 900:
                raise ValidationError('Bureau score must be between 0 and 900.')
        
        # Validate monthly income is positive
        if self.monthly_income is not None and self.monthly_income < 0:
            raise ValidationError('Monthly income must be a positive value.')
    
    def save(self, *args, **kwargs):
        """
        Override save to calculate age automatically from date of birth.
        """
        # Calculate age before saving
        if self.date_of_birth:
            self.age = calculate_age(self.date_of_birth)
        else:
            self.age = None
        
        # Run full clean validation
        self.full_clean()
        
        super().save(*args, **kwargs)
    
    @property
    def calculated_age(self):
        """
        Property to get real-time calculated age from date_of_birth.
        This ensures age is always current even if not saved recently.
        """
        return calculate_age(self.date_of_birth)
    
    def get_full_name(self):
        """
        Return the first_name and last_name, with a space in between.
        """
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_short_name(self):
        """
        Return the short name for the user (first name).
        """
        return self.first_name


class UserMeta(models.Model):
    """
    User Meta/Activity tracking table (USER LEVEL DATA B).
    Stores all activity timestamps and status tracking per user.
    This is view-only in CRM (not editable by staff).
    """
    
    # Data source choices
    DATA_SOURCE_CSV = 'CSV Upload'
    DATA_SOURCE_MANUAL = 'Manual Upload'
    DATA_SOURCE_API = 'API'
    DATA_SOURCE_CHOICES = [
        (DATA_SOURCE_CSV, 'CSV Upload'),
        (DATA_SOURCE_MANUAL, 'Manual Upload'),
        (DATA_SOURCE_API, 'API'),
    ]
    
    # Link to user (one-to-one relationship)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='meta'
    )
    
    # First added timestamps
    first_added_date = models.DateField(
        auto_now_add=True,
        help_text='Date when user was first added'
    )
    first_added_time = models.TimeField(
        auto_now_add=True,
        help_text='Time when user was first added'
    )
    
    # Last updated timestamps
    last_updated_date = models.DateField(
        auto_now=True,
        help_text='Date when user was last updated'
    )
    last_updated_time = models.TimeField(
        auto_now=True,
        help_text='Time when user was last updated'
    )
    
    # Login tracking
    first_login_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date of first login'
    )
    first_login_time = models.TimeField(
        null=True,
        blank=True,
        help_text='Time of first login'
    )
    last_login_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date of last login'
    )
    last_login_time = models.TimeField(
        null=True,
        blank=True,
        help_text='Time of last login'
    )
    
    # Disbursal tracking
    latest_disbursal_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date of latest loan disbursal'
    )
    latest_disbursal_time = models.TimeField(
        null=True,
        blank=True,
        help_text='Time of latest loan disbursal'
    )
    
    # Data download tracking
    data_last_downloaded_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date when user data was last downloaded'
    )
    data_last_downloaded_time = models.TimeField(
        null=True,
        blank=True,
        help_text='Time when user data was last downloaded'
    )
    
    # Lender status tracking (scalable for multiple lenders)
    status_lend001 = models.CharField(
        max_length=50,
        blank=True,
        help_text='Status from Lender 001'
    )
    status_lend002 = models.CharField(
        max_length=50,
        blank=True,
        help_text='Status from Lender 002'
    )
    status_lend003 = models.CharField(
        max_length=50,
        blank=True,
        help_text='Status from Lender 003'
    )
    
    # Data source tracking
    data_source = models.CharField(
        max_length=20,
        choices=DATA_SOURCE_CHOICES,
        default=DATA_SOURCE_CSV,
        help_text='How this user data was added'
    )
    data_attribution = models.CharField(
        max_length=100,
        blank=True,
        help_text='Name/source selected during upload'
    )
    
    class Meta:
        db_table = 'users_meta'
        verbose_name = 'User Meta/Activity'
        verbose_name_plural = 'User Meta/Activity Records'
        indexes = [
            models.Index(fields=['first_added_date'], name='idx_meta_added_date'),
            models.Index(fields=['last_updated_date'], name='idx_meta_updated_date'),
            models.Index(fields=['latest_disbursal_date'], name='idx_meta_disbursal'),
        ]
    
    def __str__(self):
        return f"Meta for {self.user.phone_number}"
