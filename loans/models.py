from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import date

# Create your models here.

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

class Lender(models.Model):
    """
    Enhanced Lender model with CRM-grade statistics and pincode management.
    Supports MIS tracking and whitelist/blacklist functionality.
    """
    # Lender identification
    lender_id = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text='Unique lender identifier (e.g., Lend001, Lend002)'
    )
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text='Lender name'
    )
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Statistics - Auto-updated from leads and disbursals
    total_leads = models.PositiveIntegerField(
        default=0,
        help_text='Total number of leads submitted'
    )
    total_approved = models.PositiveIntegerField(
        default=0,
        help_text='Total number of approved leads'
    )
    total_rejected = models.PositiveIntegerField(
        default=0,
        help_text='Total number of rejected leads'
    )
    total_sanctioned_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text='Total sanctioned loan amount'
    )
    total_disbursed_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text='Total disbursed loan amount'
    )
    
    # KYC statistics
    total_kyc_pan = models.PositiveIntegerField(
        default=0,
        help_text='Total PAN verifications completed'
    )
    total_kyc_aadhar = models.PositiveIntegerField(
        default=0,
        help_text='Total Aadhar verifications completed'
    )
    
    # Pincode management (JSON fields for lists)
    pincodes_whitelisted = models.JSONField(
        default=list,
        blank=True,
        help_text='List of whitelisted pincodes (allowed)'
    )
    pincodes_blacklisted = models.JSONField(
        default=list,
        blank=True,
        help_text='List of blacklisted pincodes (blocked)'
    )
    
    # MIS tracking timestamps
    mis_first_updated_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date of first MIS upload'
    )
    mis_first_updated_time = models.TimeField(
        null=True,
        blank=True,
        help_text='Time of first MIS upload'
    )
    mis_last_updated_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date of latest MIS upload'
    )
    mis_last_updated_time = models.TimeField(
        null=True,
        blank=True,
        help_text='Time of latest MIS upload'
    )
    mis_updated_by = models.CharField(
        max_length=100,
        blank=True,
        help_text='User who last updated MIS'
    )
    
    # Standard timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.lender_id} - {self.name}"
    
    def is_pincode_allowed(self, pincode):
        """
        Check if a pincode is allowed for this lender.
        If whitelist exists, pincode must be in whitelist.
        If blacklist exists, pincode must not be in blacklist.
        """
        # If whitelist exists, pincode must be in it
        if self.pincodes_whitelisted:
            return pincode in self.pincodes_whitelisted
        
        # If blacklist exists, pincode must not be in it
        if self.pincodes_blacklisted:
            return pincode not in self.pincodes_blacklisted
        
        # If neither list exists, allow all pincodes
        return True
    
    def update_statistics(self):
        """Update statistics from related leads and disbursals."""
        from django.db.models import Sum, Count, Q
        
        # Count leads by status
        leads = self.leads.aggregate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='approved')),
            rejected=Count('id', filter=Q(status='rejected'))
        )
        
        self.total_leads = leads['total'] or 0
        self.total_approved = leads['approved'] or 0
        self.total_rejected = leads['rejected'] or 0
        
        # Calculate disbursed amounts
        from .models import LoanDisbursal
        disbursals = LoanDisbursal.objects.filter(
            lead__lender=self
        ).aggregate(
            total_sanctioned=Sum('loan_amount'),
            total_disbursed=Sum('loan_amount')
        )
        
        self.total_sanctioned_amount = disbursals['total_sanctioned'] or 0
        self.total_disbursed_amount = disbursals['total_disbursed'] or 0
        
        self.save()

    class Meta:
        db_table = 'loans_lender'
        ordering = ['lender_id']
        indexes = [
            models.Index(fields=['lender_id'], name='idx_lender_id'),
        ]


class Lead(models.Model):
    """
    PRIMARY CRM Model for Leads.
    CSV uploads create Leads → Auto-generates User for authentication.
    This is the source of truth for all lead data.
    """
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
        ('Self Employed', 'Self Employed'),
        ('Student', 'Student'),
    ]

    # Primary key
    id = models.BigAutoField(primary_key=True)
    
    # Personal Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=10, db_index=True)
    email = models.EmailField(max_length=254, null=True, blank=True)
    pan_number = models.CharField(max_length=10, db_index=True, help_text='PAN format: AAAAA9999A')
    date_of_birth = models.DateField(null=True, blank=True)
    age = models.IntegerField(null=True, blank=True, editable=False)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    
    # Location
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pin_code = models.CharField(max_length=6, help_text='6 digits')
    
    # Financial Information - allow any profession text, not just choices
    profession = models.CharField(max_length=100, blank=True)
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    bureau_score = models.IntegerField(null=True, blank=True, db_index=True, help_text='Credit score 0-900')
    
    # Consent
    consent_taken = models.BooleanField(default=False)
    
    # Status (generic status, not tied to any lender)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.status})"
    
    @property
    def calculated_age(self):
        """
        Property to get real-time calculated age from date_of_birth.
        This ensures age is always current even if not saved recently.
        """
        return calculate_age_from_dob(self.date_of_birth)

    class Meta:
        db_table = 'loans_lead'
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number', 'pan_number'], name='idx_lead_phone_pan'),
            models.Index(fields=['status'], name='idx_lead_status'),
            models.Index(fields=['bureau_score'], name='idx_lead_bureau'),
        ]
        # Note: Removed lender-based uniqueness constraints since lender is now optional
        # A lead can exist without a lender, but phone and PAN should be globally unique
        constraints = [
            models.UniqueConstraint(
                fields=['phone_number'],
                name='unique_phone_number'
            ),
            models.UniqueConstraint(
                fields=['pan_number'],
                name='unique_pan_number'
            ),
        ]
    
    def save(self, *args, **kwargs):
        # Calculate age from date_of_birth before saving
        if self.date_of_birth:
            self.age = calculate_age_from_dob(self.date_of_birth)
        else:
            self.age = None
        super().save(*args, **kwargs)


@receiver(post_save, sender=Lead)
def create_user_from_lead(sender, instance, created, **kwargs):
    """
    IMPORTANT: Auto-create/update User when Lead is created/updated.
    Lead is source of truth → User is created for authentication.
    Also updates UserMeta with data_source tracking.
    """
    from users.models import User, UserMeta
    from django.core.exceptions import ValidationError
    
    # Check if user exists by phone number
    try:
        user = User.objects.get(phone_number=instance.phone_number)
        
        # Use QuerySet.update() to bypass all validation and signals
        User.objects.filter(pk=user.pk).update(
            first_name=instance.first_name,
            last_name=instance.last_name,
            email=instance.email or user.email,
            pan_number=instance.pan_number,
            pin_code=instance.pin_code,
            gender=instance.gender or user.gender,
            date_of_birth=instance.date_of_birth or user.date_of_birth,
            age=calculate_age_from_dob(instance.date_of_birth or user.date_of_birth),
            city=instance.city or user.city,
            state=instance.state or user.state,
            profession=instance.profession or user.profession,
            monthly_income=instance.monthly_income or user.monthly_income,
            bureau_score=instance.bureau_score or user.bureau_score,
            consent_taken=instance.consent_taken
        )
        
        # Update UserMeta if data source not set
        try:
            meta = user.meta
            if not meta.data_source:
                meta.data_source = 'Lead Upload'
                meta.data_attribution = 'Direct Lead Entry'
                meta.save()
        except UserMeta.DoesNotExist:
            # Create UserMeta if it doesn't exist (should be auto-created by signal)
            UserMeta.objects.create(
                user=user,
                data_source='Lead Upload',
                data_attribution='Direct Lead Entry'
            )
    except User.DoesNotExist:
        # Create new user from lead
        user = User.objects.create(
            phone_number=instance.phone_number,
            first_name=instance.first_name,
            last_name=instance.last_name,
            email=instance.email,
            pan_number=instance.pan_number,
            pin_code=instance.pin_code,
            gender=instance.gender,
            date_of_birth=instance.date_of_birth,
            city=instance.city,
            state=instance.state,
            profession=instance.profession,
            monthly_income=int(instance.monthly_income) if instance.monthly_income else None,
            bureau_score=instance.bureau_score,
            consent_taken=instance.consent_taken,
        )
        
        # Set UserMeta data source for new user
        try:
            meta = user.meta
            meta.data_source = 'Lead Upload'
            meta.data_attribution = 'Direct Lead Entry'
            meta.save()
        except UserMeta.DoesNotExist:
            UserMeta.objects.create(
                user=user,
                data_source='Lead Upload',
                data_attribution='Direct Lead Entry'
            )


class LoanDisbursal(models.Model):
    """Model for Loan Disbursals - linked to Lead"""
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='disbursals',
        help_text='Lead for whom loan was disbursed'
    )
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2)
    disbursed_date = models.DateField()
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    tenure_months = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Loan ₹{self.loan_amount} - {self.lead.first_name} {self.lead.last_name}"

    class Meta:
        db_table = 'loans_loandisbursal'
        ordering = ['-disbursed_date']
        indexes = [
            models.Index(fields=['disbursed_date'], name='idx_disbursal_date'),
            models.Index(fields=['lead', 'disbursed_date'], name='idx_lead_disbursal'),
        ]


class LenderMIS(models.Model):
    """
    Lender MIS (Management Information System) Upload Model.
    Stores raw MIS data uploaded by lenders.
    Each row represents one lead's data as provided by the lender.
    """
    # Unique identifier for each MIS record
    lead_id = models.UUIDField(
        unique=True,
        help_text='Unique UUID for this MIS record'
    )
    lead_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date when lead was generated'
    )
    
    # Status tracking
    status = models.CharField(
        max_length=50,
        blank=True,
        help_text='Current status of the lead (e.g., pending, approved, rejected)'
    )
    ptb_status = models.CharField(
        max_length=50,
        blank=True,
        help_text='PTB (Pre-Trade Booking) status'
    )
    reject_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date when lead was rejected'
    )
    
    # UTM tracking
    utm_campaign = models.CharField(
        max_length=200,
        blank=True,
        help_text='UTM campaign parameter'
    )
    utm_source = models.CharField(
        max_length=200,
        blank=True,
        help_text='UTM source parameter'
    )
    
    # Customer information
    mobile_number = models.CharField(
        max_length=10,
        db_index=True,
        help_text='Customer mobile number'
    )
    name = models.CharField(
        max_length=200,
        blank=True,
        help_text='Customer full name'
    )
    
    # KYC status
    selfie_done = models.BooleanField(
        default=False,
        help_text='Whether selfie verification is completed'
    )
    aadhar_done = models.BooleanField(
        default=False,
        help_text='Whether Aadhar verification is completed'
    )
    pan_verified = models.BooleanField(
        default=False,
        help_text='Whether PAN verification is completed'
    )
    
    # Customer details
    profession = models.CharField(
        max_length=100,
        blank=True,
        help_text='Customer profession'
    )
    salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Customer monthly salary'
    )
    dob = models.DateField(
        null=True,
        blank=True,
        help_text='Customer date of birth'
    )
    pincode = models.CharField(
        max_length=6,
        blank=True,
        help_text='Customer pincode'
    )
    
    # Loan details
    sanctioned_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Sanctioned loan amount'
    )
    loan_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Actual loan amount'
    )
    disbursed_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Amount actually disbursed'
    )
    disbursed_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date when loan was disbursed'
    )
    
    # Foreign keys
    lender = models.ForeignKey(
        Lender,
        on_delete=models.CASCADE,
        related_name='mis_records',
        help_text='Lender who uploaded this MIS record'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mis_records',
        help_text='User linked to this MIS record (via mobile number)'
    )
    
    # Upload tracking
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When this MIS record was uploaded'
    )
    uploaded_by = models.CharField(
        max_length=100,
        blank=True,
        help_text='User who uploaded this MIS record'
    )
    
    class Meta:
        db_table = 'loans_lender_mis'
        verbose_name = 'Lender MIS Record'
        verbose_name_plural = 'Lender MIS Records'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['mobile_number'], name='idx_mis_mobile'),
            models.Index(fields=['lender', 'mobile_number'], name='idx_mis_lender_mobile'),
            models.Index(fields=['lead_date'], name='idx_mis_lead_date'),
            models.Index(fields=['disbursed_date'], name='idx_mis_disburse_date'),
            models.Index(fields=['status'], name='idx_mis_status'),
        ]
    
    def __str__(self):
        return f"MIS {self.lead_id} - {self.mobile_number} ({self.lender.lender_id})"
    
    def link_user(self):
        """Automatically link this MIS record to a User based on mobile number."""
        from users.models import User
        try:
            self.user = User.objects.get(phone_number=self.mobile_number)
            self.save()
        except User.DoesNotExist:
            pass
