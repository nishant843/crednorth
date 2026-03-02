from django.contrib import admin
from .models import LoanDisbursal
# Lender and LenderMIS have been moved to lenders app - see lenders/admin.py


@admin.register(LoanDisbursal)
class LoanDisbursalAdmin(admin.ModelAdmin):
    """Admin for Loan Disburs als - linked to Users"""
    list_display = (
        'id', 'get_user_info', 'loan_amount', 'disbursed_date',
        'interest_rate', 'tenure_months', 'created_at'
    )
    search_fields = (
        'user__first_name', 'user__last_name',
        'user__phone_number', 'user__pan_number'
    )
    list_filter = ('disbursed_date', 'created_at')
    raw_id_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')
    
    def get_user_info(self, obj):
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name} ({obj.user.phone_number})"
        return "N/A"
    get_user_info.short_description = 'User'
