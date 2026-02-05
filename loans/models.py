from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Lender(models.Model):
    """Model for Lenders"""
    name = models.CharField(max_length=200, unique=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Lead(models.Model):
    """Model for Leads"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    pan = models.CharField(max_length=10)
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    pin_code = models.CharField(max_length=10)
    income = models.DecimalField(max_digits=12, decimal_places=2)
    employment_type = models.CharField(max_length=50)
    lender = models.ForeignKey(Lender, on_delete=models.CASCADE, related_name='leads')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.lender.name}"

    class Meta:
        ordering = ['-created_at']


class LoanDisbursal(models.Model):
    """Model for Loan Disbursals"""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='disbursals')
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2)
    disbursed_date = models.DateField()
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    tenure_months = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Loan {self.loan_amount} - {self.lead.first_name} {self.lead.last_name}"

    class Meta:
        ordering = ['-disbursed_date']
