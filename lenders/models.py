from django.db import models
from django.conf import settings
from datetime import date


class Lender(models.Model):
    """
    Enhanced Lender model with CRM-grade statistics and pincode management.
    Supports MIS tracking and whitelist/blacklist functionality.
    """
    # Primary key
    id = models.BigAutoField(primary_key=True)
    
    # Lender identification
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text='Lender name'
    )
    
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
    total_sanctioned_loan_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text='Total sanctioned loan amount'
    )
    total_loan_amount_disbursed = models.DecimalField(
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
    mis_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lender_mis_updates',
        help_text='User who last updated MIS'
    )
    
    # Standard timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (ID: {self.id})"
    
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
        # NOTE: This method is currently non-functional as there is no direct
        # relationship between Lender and User models in the current schema.
        # If you need lender statistics, you'll need to:
        # 1. Add a lender ForeignKey field to the User model, OR
        # 2. Create a LeadLender junction table for many-to-many relationships
        from django.db.models import Sum, Count, Q
        from loans.models import LoanDisbursal
        
        # Placeholder implementation - no leads associated with lenders currently
        self.total_leads = 0
        self.total_approved = 0
        self.total_rejected = 0
        self.total_sanctioned_loan_amount = 0
        self.total_loan_amount_disbursed = 0
        
        self.save()

    class Meta:
        db_table = 'loans_lender'
        ordering = ['name']


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
        'Lender',
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
        return f"MIS {self.lead_id} - {self.mobile_number} (Lender ID: {self.lender.id})"
    
    def link_user(self):
        """Automatically link this MIS record to a User based on mobile number."""
        from users.models import User
        try:
            self.user = User.objects.get(phone_number=self.mobile_number)
            self.save()
        except User.DoesNotExist:
            pass
