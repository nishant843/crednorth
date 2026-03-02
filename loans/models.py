from django.db import models
from django.conf import settings
from datetime import date

# Import Lender and LenderMIS from lenders app
from lenders.models import Lender, LenderMIS

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


# Lender and LenderMIS models have been moved to the 'lenders' app
# See lenders/models.py for these models
# They are imported above for backward compatibility


class LoanDisbursal(models.Model):
    """Model for Loan Disbursals - linked to User"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='disbursals',
        help_text='User for whom loan was disbursed',
        null=True,  # Temporarily nullable for migration
        blank=True
    )
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2)
    disbursed_date = models.DateField()
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    tenure_months = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Loan ₹{self.loan_amount} - {self.user.first_name} {self.user.last_name}"

    class Meta:
        db_table = 'loans_loandisbursal'
        ordering = ['-disbursed_date']
        indexes = [
            models.Index(fields=['disbursed_date'], name='idx_disbursal_date'),
            models.Index(fields=['user', 'disbursed_date'], name='idx_user_disbursal'),
        ]
