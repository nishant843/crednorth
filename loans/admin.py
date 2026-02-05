from django.contrib import admin
from .models import Lender, Lead, LoanDisbursal

# Register your models here.

@admin.register(Lender)
class LenderAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'contact_email', 'contact_phone', 'created_at')
    search_fields = ('name', 'contact_email')
    list_filter = ('created_at',)


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'last_name', 'phone_number', 'pan', 'lender', 'status', 'created_at')
    search_fields = ('first_name', 'last_name', 'phone_number', 'pan')
    list_filter = ('status', 'lender', 'employment_type', 'created_at')
    raw_id_fields = ('lender',)


@admin.register(LoanDisbursal)
class LoanDisbursalAdmin(admin.ModelAdmin):
    list_display = ('id', 'lead', 'loan_amount', 'disbursed_date', 'interest_rate', 'tenure_months', 'created_at')
    search_fields = ('lead__first_name', 'lead__last_name', 'lead__pan')
    list_filter = ('disbursed_date', 'created_at')
    raw_id_fields = ('lead',)
