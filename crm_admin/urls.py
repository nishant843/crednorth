from django.urls import path
from .views import (
    BulkDedupeAPIView,
    CRMDashboardView,
    CRMLendersView,
    CRMDisbursalsView,
    CRMFetchDataView,
    DisbursalCreateView,
    DisbursalDeleteView,
    LenderCreateView,
    CSVValidateView,
    BulkUploadView,
    ExportLeadsView,
    LeadDetailView,
    LeadUpdateView,
    LeadDeleteView
)

app_name = 'crm_admin'

urlpatterns = [
    # Main dashboard routes
    path('', CRMDashboardView.as_view(), name='dashboard'),
    path('users/', CRMDashboardView.as_view(), name='users'),
    path('lenders/', CRMLendersView.as_view(), name='lenders'),
    path('disbursals/', CRMDisbursalsView.as_view(), name='disbursals'),
    path('fetch-data/', CRMFetchDataView.as_view(), name='fetch_data'),
    
    # Bulk operations
    path('bulk-dedupe/', BulkDedupeAPIView.as_view(), name='bulk_dedupe'),
    
    # Lead operations
    path('leads/validate-csv/', CSVValidateView.as_view(), name='csv_validate'),
    path('leads/bulk-upload/', BulkUploadView.as_view(), name='bulk_upload'),
    path('leads/export/', ExportLeadsView.as_view(), name='export_leads'),
    path('leads/<int:lead_id>/', LeadDetailView.as_view(), name='lead_detail'),
    path('leads/<int:lead_id>/update/', LeadUpdateView.as_view(), name='lead_update'),
    path('leads/<int:lead_id>/delete/', LeadDeleteView.as_view(), name='lead_delete'),
    
    # Disbursal operations
    path('disbursals/create/', DisbursalCreateView.as_view(), name='disbursal_create'),
    path('disbursals/<int:disbursal_id>/delete/', DisbursalDeleteView.as_view(), name='disbursal_delete'),
    
    # Lender operations
    path('lenders/create/', LenderCreateView.as_view(), name='lender_create'),
]
