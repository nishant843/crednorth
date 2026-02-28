from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from loans.models import Lender, Lead, LoanDisbursal
from datetime import date, timedelta
from decimal import Decimal
import random


class Command(BaseCommand):
    help = 'Populate database with sample data for CRM dashboard'

    def handle(self, *args, **options):
        self.stdout.write('Creating sample data...')

        # Create superuser if doesn't exist
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
            self.stdout.write(self.style.SUCCESS('Created superuser: admin/admin123'))

        # Create lenders
        lenders_data = [
            {'name': 'HDFC Bank', 'contact_email': 'loans@hdfc.com', 'contact_phone': '1800-267-4343'},
            {'name': 'ICICI Bank', 'contact_email': 'support@icici.com', 'contact_phone': '1860-120-7777'},
            {'name': 'Axis Bank', 'contact_email': 'info@axisbank.com', 'contact_phone': '1860-419-5555'},
            {'name': 'Bajaj Finserv', 'contact_email': 'care@bajajfinserv.in', 'contact_phone': '020-3957-5152'},
            {'name': 'Tata Capital', 'contact_email': 'customercare@tatacapital.com', 'contact_phone': '1800-209-8282'},
        ]

        lenders = []
        for lender_data in lenders_data:
            lender, created = Lender.objects.get_or_create(
                name=lender_data['name'],
                defaults={
                    'contact_email': lender_data['contact_email'],
                    'contact_phone': lender_data['contact_phone']
                }
            )
            lenders.append(lender)
            if created:
                self.stdout.write(f'Created lender: {lender.name}')

        # Create leads
        first_names = ['Amit', 'Priya', 'Rahul', 'Sneha', 'Vikas', 'Neha', 'Arjun', 'Pooja', 'Ravi', 'Anita', 
                      'Suresh', 'Kavita', 'Arun', 'Divya', 'Manoj', 'Shweta', 'Vikram', 'Rani', 'Karan', 'Meera']
        last_names = ['Sharma', 'Kumar', 'Singh', 'Patel', 'Gupta', 'Verma', 'Reddy', 'Shah', 'Joshi', 'Nair']
        
        leads = []
        for i in range(50):
            lead = Lead.objects.create(
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                phone_number=f'9{random.randint(100000000, 999999999)}',
                pan=f'{"".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=5))}{random.randint(1000, 9999)}{"".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=1))}',
                dob=date(random.randint(1970, 2000), random.randint(1, 12), random.randint(1, 28)),
                gender=random.choice(['male', 'female']),
                pin_code=str(random.randint(100000, 999999)),
                income=Decimal(random.randint(25000, 150000)),
                employment_type=random.choice(['salaried', 'self-employed']),
                lender=random.choice(lenders),
                status=random.choice(['pending', 'approved', 'rejected'])
            )
            leads.append(lead)
        
        self.stdout.write(self.style.SUCCESS(f'Created {len(leads)} leads'))

        # Create loan disbursals for approved leads
        approved_leads = [lead for lead in leads if lead.status == 'approved']
        disbursals = []
        
        for lead in approved_leads[:30]:  # Create disbursals for some approved leads
            disbursal = LoanDisbursal.objects.create(
                lead=lead,
                loan_amount=Decimal(random.randint(50000, 1000000)),
                disbursed_date=date.today() - timedelta(days=random.randint(1, 365)),
                interest_rate=Decimal(random.uniform(8.5, 18.0)).quantize(Decimal('0.01')),
                tenure_months=random.choice([12, 24, 36, 48, 60])
            )
            disbursals.append(disbursal)
        
        self.stdout.write(self.style.SUCCESS(f'Created {len(disbursals)} loan disbursals'))
        
        self.stdout.write(self.style.SUCCESS('\nSample data creation complete!'))
        self.stdout.write(self.style.SUCCESS(f'Total Lenders: {len(lenders)}'))
        self.stdout.write(self.style.SUCCESS(f'Total Leads: {len(leads)}'))
        self.stdout.write(self.style.SUCCESS(f'Total Disbursals: {len(disbursals)}'))
        self.stdout.write(self.style.WARNING('\nYou can now login with:'))
        self.stdout.write(self.style.WARNING('Username: admin'))
        self.stdout.write(self.style.WARNING('Password: admin123'))
