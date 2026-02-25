from django.contrib import admin
from django.utils.html import format_html
from .models import Lender, Lead, LoanDisbursal, LenderMIS

# Register your models here.

@admin.register(Lender)
class LenderAdmin(admin.ModelAdmin):
    """
    Enhanced Lender Admin with CRM-grade statistics and management.
    Supports pincode whitelist/blacklist and MIS tracking.
    """
    list_display = (
        'lender_id',
        'name',
        'total_leads',
        'total_approved',
        'total_rejected',
        'approval_rate',
        'total_disbursed_amount',
        'contact_email',
        'created_at',
    )
    
    search_fields = ('lender_id', 'name', 'contact_email')
    
    list_filter = (
        'mis_last_updated_date',
        'created_at',
    )
    
    readonly_fields = (
        'total_leads',
        'total_approved',
        'total_rejected',
        'total_sanctioned_amount',
        'total_disbursed_amount',
        'total_kyc_pan',
        'total_kyc_aadhar',
        'created_at',
        'updated_at',
    )
    
    fieldsets = (
        ('Identification', {
            'fields': ('lender_id', 'name')
        }),
        ('Contact Information', {
            'fields': ('contact_email', 'contact_phone')
        }),
        ('Statistics (Auto-Calculated)', {
            'fields': (
                'total_leads',
                'total_approved',
                'total_rejected',
                'total_sanctioned_amount',
                'total_disbursed_amount',
                'total_kyc_pan',
                'total_kyc_aadhar',
            )
        }),
        ('Pincode Management', {
            'fields': (
                'pincodes_whitelisted',
                'pincodes_blacklisted',
            ),
            'description': 'Manage allowed/blocked pincodes. Leave empty to allow all.'
        }),
        ('MIS Tracking', {
            'fields': (
                'mis_first_updated_date',
                'mis_first_updated_time',
                'mis_last_updated_date',
                'mis_last_updated_time',
                'mis_updated_by',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['refresh_statistics']
    
    def approval_rate(self, obj):
        """Calculate and display approval rate."""
        if obj.total_leads > 0:
            rate = (obj.total_approved / obj.total_leads) * 100
            color = 'green' if rate >= 50 else 'orange' if rate >= 25 else 'red'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
                color, rate
            )
        return '-'
    approval_rate.short_description = 'Approval Rate'
    
    def refresh_statistics(self, request, queryset):
        """Manually refresh statistics for selected lenders."""
        for lender in queryset:
            lender.update_statistics()
        self.message_user(request, f'Statistics refreshed for {queryset.count()} lender(s).')
    refresh_statistics.short_description = 'Refresh statistics'


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    """Admin for Leads - PRIMARY CRM model (potential customers database)"""
    list_display = (
        'id', 'first_name', 'last_name', 'phone_number', 'pan_number',
        'status', 'bureau_score', 'monthly_income', 'created_at'
    )
    search_fields = (
        'first_name', 'last_name', 'phone_number', 'pan_number', 'email'
    )
    list_filter = ('status', 'profession', 'gender', 'consent_taken', 'created_at')
    readonly_fields = ('age', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'phone_number', 'email', 'gender', 'date_of_birth', 'age')
        }),
        ('Identity', {
            'fields': ('pan_number',)
        }),
        ('Location', {
            'fields': ('pin_code', 'city', 'state')
        }),
        ('Financial', {
            'fields': ('profession', 'monthly_income', 'bureau_score')
        }),
        ('Consent & Status', {
            'fields': ('consent_taken', 'status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(LoanDisbursal)
class LoanDisbursalAdmin(admin.ModelAdmin):
    """Admin for Loan Disbursals - linked to Leads"""
    list_display = (
        'id', 'get_lead_info', 'loan_amount', 'disbursed_date',
        'interest_rate', 'tenure_months', 'created_at'
    )
    search_fields = (
        'lead__first_name', 'lead__last_name',
        'lead__phone_number', 'lead__pan_number'
    )
    list_filter = ('disbursed_date', 'created_at')
    raw_id_fields = ('lead',)
    readonly_fields = ('created_at', 'updated_at')
    
    def get_lead_info(self, obj):
        if obj.lead:
            return f"{obj.lead.first_name} {obj.lead.last_name} ({obj.lead.phone_number})"
        return "N/A"
    get_lead_info.short_description = 'Lead'


@admin.register(LenderMIS)
class LenderMISAdmin(admin.ModelAdmin):
    """
    Admin for Lender MIS (Management Information System) records.
    Displays raw upload data from lenders with comprehensive filtering.
    """
    list_display = (
        'lead_id',
        'mobile_number',
        'name',
        'lender',
        'status',
        'pan_verified',
        'aadhar_done',
        'disbursed_amount',
        'disbursed_date',
        'uploaded_at',
    )
    
    search_fields = (
        'lead_id',
        'mobile_number',
        'name',
        'pincode',
        'lender__name',
        'lender__lender_id',
    )
    
    list_filter = (
        'lender',
        'status',
        'ptb_status',
        'pan_verified',
        'aadhar_done',
        'selfie_done',
        'lead_date',
        'disbursed_date',
        'uploaded_at',
    )
    
    readonly_fields = ('uploaded_at',)
    
    raw_id_fields = ('lender', 'user')
    
    date_hierarchy = 'uploaded_at'
    
    list_per_page = 100
    
    fieldsets = (
        ('Record Identification', {
            'fields': ('lead_id', 'lead_date', 'lender', 'user')
        }),
        ('Status Tracking', {
            'fields': ('status', 'ptb_status', 'reject_date')
        }),
        ('UTM Tracking', {
            'fields': ('utm_campaign', 'utm_source')
        }),
        ('Customer Information', {
            'fields': ('mobile_number', 'name', 'dob', 'pincode', 'profession', 'salary')
        }),
        ('KYC Status', {
            'fields': ('selfie_done', 'aadhar_done', 'pan_verified')
        }),
        ('Loan Details', {
            'fields': (
                'sanctioned_amount',
                'loan_amount',
                'disbursed_amount',
                'disbursed_date',
            )
        }),
        ('Upload Tracking', {
            'fields': ('uploaded_at', 'uploaded_by')
        }),
    )
    
    actions = ['link_to_users']
    
    def link_to_users(self, request, queryset):
        """Link MIS records to users based on mobile number."""
        linked = 0
        for mis in queryset:
            if not mis.user:
                mis.link_user()
                if mis.user:
                    linked += 1
        self.message_user(request, f'{linked} MIS record(s) linked to users.')
    link_to_users.short_description = 'Link to Users (by mobile)'
