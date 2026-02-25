# Architecture Refactor: Users ARE Leads

## Critical Design Principle
**Users ARE Leads** - There is no separate Lead entity. Every user is a potential lead.

## Previous Architecture (DEPRECATED)
```
┌─────────┐         ┌──────────────┐
│ User    │         │ Lead         │ (Duplicate personal data)
│ ┌────── │         │ ┌──────────  │
│ │ Auth  │         │ │ Name       │
│ │ Data  │         │ │ Phone      │
│ └────── │         │ │ PAN        │
└─────────┘         │ │ Income     │
                    │ │ Profession │
                    │ └──────────  │
                    │ ┌──────────  │
                    │ │ Lender     │
                    │ │ Status     │
                    │ └──────────  │
                    └──────────────┘
                          │
                          ▼
                    ┌─────────────┐
                    │ Disbursal   │
                    └─────────────┘
```

**Problems:**
- Data duplication (Name, Phone, PAN, etc. in both User and Lead)
- Inconsistency when user data changes
- Confusing data model
- Two sources of truth

## New Architecture (CURRENT)
```
┌──────────────────┐
│ User (= Lead)    │  ← Single source of truth
│ ┌──────────────  │
│ │ Auth Data      │
│ │ Personal Info  │
│ │ Financial Info │
│ │ Bureau Score   │
│ │ Consent        │
│ └──────────────  │
└──────────────────┘
          │
          │ applies to
          ▼
┌──────────────────┐
│ LoanApplication  │  ← User applying to Lender
│ ┌──────────────  │
│ │ User (FK)      │
│ │ Lender (FK)    │
│ │ Status         │
│ │ Amount         │
│ └──────────────  │
└──────────────────┘
          │
          │ if approved
          ▼
┌──────────────────┐
│ LoanDisbursal    │
│ ┌──────────────  │
│ │ Application    │
│ │ Amount         │
│ │ Date           │
│ │ Interest Rate  │
│ └──────────────  │
└──────────────────┘
```

**Benefits:**
- No data duplication
- Single source of truth for user/lead data
- Clearer relationships
- Easier to scale

## Model Changes

### 1. User Model (users/models.py)
**Status:** Unchanged - Already the correct design
- Contains all personal and CRM data
- Used for both authentication AND lead management
- Fields: phone, name, PAN, income, profession, bureau_score, consent, etc.

### 2. LoanApplication Model (NEW - loans/models.py)
**Purpose:** Track user applications to different lenders
```python
class LoanApplication(models.Model):
    user = ForeignKey(User)           # The lead applying
    lender = ForeignKey(Lender)       # Which lender
    status = CharField(choices=...)   # pending/approved/rejected
    applied_amount = DecimalField()   # Requested amount
    created_at = DateTimeField()
    
    # Constraint: One application per user-lender pair
    unique_together = [('user', 'lender')]
```

### 3. Lead Model (DEPRECATED - loans/models.py)
**Status:** Kept for backwards compatibility during migration
- Marked as deprecated
- Will be removed in future version
- All CRUD operations disabled

### 4. LoanDisbursal Model (UPDATED - loans/models.py)
**Changes:**
- Now links to `LoanApplication` instead of `Lead`
- Has `@property user` to get user from application
- Backwards compatible with old `lead` field during migration

## View Changes

### New Views Created:
1. **LoanApplicationCreateView** - Create application (User → Lender)
2. **LoanApplicationUpdateView** - Update application status
3. **LoanApplicationDeleteView** - Delete application

### Deprecated Views:
1. **LeadCreateView** - Returns error: "Users ARE Leads"
2. **LeadUpdateView** - Returns error: "Update User directly"
3. **LeadDeleteView** - Returns error: "Delete User directly"

### Updated Views:
1. **CRMDashboardView**
   - Now treats `User` as leads
   - Shows `LoanApplication` instead of Lead
   - Statistics updated to reflect new architecture
   - Filters work on User model fields

2. **DisbursalCreateView**
   - Now links to `LoanApplication` instead of `Lead`

## Admin Interface Changes

### New Admin:
- **LoanApplicationAdmin** - Manage loan applications
  - Shows user phone, name, PAN
  - Filterable by lender, status
  - Searchable by user fields

### Updated Admin:
- **LeadAdmin** - Made read-only (deprecated)
- **LoanDisbursalAdmin** - Shows user info from application

## Migration Strategy

### Migration Files Created:
1. **0002_alter_loandisbursal_lead_loanapplication_and_more.py**
   - Creates LoanApplication table
   - Adds application field to LoanDisbursal
   - Makes lead field nullable

2. **0003_migrate_leads_to_users.py**
   - Data migration to convert Leads → Users + LoanApplications
   - Steps:
     a. For each Lead, create or update User (dedupe by phone)
     b. Create LoanApplication for User → Lender
     c. Link LoanDisbursals to new LoanApplications

### Migration Safety:
- Old Lead model kept temporarily for reference
- Old lead field in LoanDisbursal kept temporarily
- Can rollback if needed (though not recommended)

## URL Changes

### New Routes:
```python
# Loan Applications
path('applications/create/', LoanApplicationCreateView.as_view())
path('applications/<int:application_id>/update/', LoanApplicationUpdateView.as_view())
path('applications/<int:application_id>/delete/', LoanApplicationDeleteView.as_view())
```

### Deprecated Routes:
```python
# These now return deprecation errors
path('leads/create/', LeadCreateView.as_view())  # ❌
path('leads/<int:lead_id>/update/', LeadUpdateView.as_view())  # ❌
path('leads/<int:lead_id>/delete/', LeadDeleteView.as_view())  # ❌
```

## Template Changes

### Variables Renamed:
- `recent_leads` → Shows `LoanApplication` objects (for compatibility)
- `recent_applications` → Shows `LoanApplication` objects (new name)
- `total_leads` → Total loan applications count
- `total_users` → Total leads (users) count

### Context Now Includes:
```python
{
    'total_users': ...,          # Total leads
    'total_applications': ...,   # Total loan applications
    'recent_users': ...,         # Recent leads (User objects)
    'recent_applications': ...,  # Recent loan applications
    'recent_leads': ...,         # Alias for recent_applications
}
```

## API/Service Changes

### Bulk Upload:
- CSV uploads create/update **Users** (the actual leads)
- No separate lead creation needed
- User CSV has all personal/financial fields

### Future: Loan Application Bulk Upload:
- Can add CSV upload for creating LoanApplications
- Format: `phone_number,lender_name,status,amount`
- Links existing users to lenders

## Best Practices Going Forward

### Creating New Leads:
```python
# ✅ Correct: Create User
user = User.objects.create(
    phone_number='9876543210',
    first_name='John',
    last_name='Doe',
    pan_number='ABCPM1234Z',
    pin_code='110001',
    monthly_income=50000,
    profession='Salaried'
)

# ✅ Create application to lender
application = LoanApplication.objects.create(
    user=user,
    lender=lender,
    status='pending',
    applied_amount=100000
)

# ❌ Wrong: Don't create Lead objects
lead = Lead.objects.create(...)  # This is deprecated!
```

### Querying Leads:
```python
# ✅ Correct: Query Users (they ARE leads)
leads = User.objects.filter(bureau_score__gte=750)
leads_with_consent = User.objects.filter(consent_taken=True)

# ❌ Wrong: Don't query Lead model
leads = Lead.objects.all()  # This is deprecated!
```

### Checking Applications:
```python
# ✅ Correct: Query LoanApplications
user_applications = user.loan_applications.all()
pending_apps = LoanApplication.objects.filter(status='pending')
lender_apps = LoanApplication.objects.filter(lender=lender)

# ✅ Get user from application
application = LoanApplication.objects.get(id=1)
user = application.user  # The lead
```

### Creating Disbursals:
```python
# ✅ Correct: Link to LoanApplication
disbursal = LoanDisbursal.objects.create(
    application=application,
    loan_amount=100000,
    disbursed_date='2026-02-14',
    interest_rate=12.5,
    tenure_months=36
)

# Access user
user = disbursal.user  # Via @property

# ❌ Wrong: Don't link to Lead
disbursal = LoanDisbursal.objects.create(lead=lead, ...)  # Deprecated!
```

## Database Schema

### Tables:
1. **users_user** - Main table (Users/Leads)
   - All personal and financial data
   - Indexed: phone_number, pan_number, pin_code, bureau_score

2. **loans_loanapplication** - User → Lender applications
   - ForeignKey to users_user
   - ForeignKey to loans_lender
   - Unique constraint: (user, lender)

3. **loans_loandisbursal** - Actual loan disbursements
   - ForeignKey to loans_loanapplication
   - Tracks disbursed amount, date, terms

4. **loans_lead** (DEPRECATED) - Will be removed
   - Kept temporarily for migration
   - Read-only in admin

## Testing

### Check System Health:
```bash
python manage.py check
# System check identified no issues (0 silenced). ✓
```

### Test Migrations:
```bash
python manage.py migrate loans
# All migrations applied successfully ✓
```

### Test Admin:
1. Go to `/admin/loans/loanapplication/`
2. Create application: Select User + Lender
3. Verify unique constraint works (duplicate prevented)

### Test CRM Dashboard:
1. Go to `/admin-crm-dashboard/`
2. Upload user CSV (creates leads)
3. View users in User Management section
4. Apply filters (gender, profession, income)
5. Search by phone/name/PAN

## Migration Completion Checklist

- [x] Create LoanApplication model
- [x] Update LoanDisbursal to reference LoanApplication
- [x] Create schema migration
- [x] Create data migration
- [x] Run migrations
- [x] Update admin interface
- [x] Update views (GET/POST handlers)
- [x] Deprecate old Lead CRUD views
- [x] Update DisbursalCreateView
- [x] Test Django check (no errors)
- [x] Document architecture change
- [ ] Update templates (if Lead references exist)
- [ ] Update frontend JavaScript (if any)
- [ ] Update services/bulk_processor (if needed)
- [ ] Remove old Lead model (future release)

## Backwards Compatibility

### Temporary Support:
- Lead model still exists (read-only)
- Old lead field in LoanDisbursal still exists
- Data migration handles old data

### Breaking Changes:
- LeadCreateView returns error
- LeadUpdateView returns error
- LeadDeleteView returns error
- CSV format no longer creates Lead records (creates Users)

### Deprecation Timeline:
1. **Now**: New architecture active, old model deprecated
2. **Next Release**: Remove Lead model entirely
3. **Future**: Remove old lead field from LoanDisbursal

## Troubleshooting

### "Lead object has no attribute X"
**Solution:** Use User object instead. Users ARE Leads.

### "Can't create Lead"
**Solution:** Create User instead. To link to lender, create LoanApplication.

### "No recent_leads in template"
**Solution:** Check context - it now contains LoanApplication objects.

### "Migration fails"
**Solution:** Ensure users app is migrated first. Check phone number formats.

## Summary

**Key Takeaway:** **Users ARE Leads**

- Don't create separate Lead records
- User model contains ALL lead data
- LoanApplication tracks user-lender relationships  
- This eliminates duplication and scales better

All admin operations should now use:
- **User** for lead management (personal data)
- **LoanApplication** for tracking applications to lenders
- **LoanDisbursal** for tracking actual loans disbursed

