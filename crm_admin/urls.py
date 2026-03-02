from django.urls import path
from .views import (
    BulkDedupeAPIView,
    CRMDashboardView,
    CRMLendersView,
    CRMFetchDataView,
    LenderCreateView,
    LenderDetailView,
    LenderUpdateView,
    LenderDeleteView,
    CSVValidateView,
    BulkUploadView,
    DownloadSampleCSVView,
    ExportLeadsView,
    LeadCreateView,
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
    path('fetch-data/', CRMFetchDataView.as_view(), name='fetch_data'),
    
    # Bulk operations
    path('bulk-dedupe/', BulkDedupeAPIView.as_view(), name='bulk_dedupe'),
    
    # Lead operations
    path('leads/create/', LeadCreateView.as_view(), name='lead_create'),
    path('leads/validate-csv/', CSVValidateView.as_view(), name='csv_validate'),
    path('leads/bulk-upload/', BulkUploadView.as_view(), name='bulk_upload'),
    path('leads/download-sample-csv/', DownloadSampleCSVView.as_view(), name='download_sample_csv'),
    path('leads/export/', ExportLeadsView.as_view(), name='export_leads'),
    path('leads/<int:lead_id>/', LeadDetailView.as_view(), name='lead_detail'),
    path('leads/<int:lead_id>/update/', LeadUpdateView.as_view(), name='lead_update'),
    path('leads/<int:lead_id>/delete/', LeadDeleteView.as_view(), name='lead_delete'),
    
    # Lender operations
    path('lenders/create/', LenderCreateView.as_view(), name='lender_create'),
    path('lenders/<int:lender_id>/', LenderDetailView.as_view(), name='lender_detail'),
    path('lenders/<int:lender_id>/update/', LenderUpdateView.as_view(), name='lender_update'),
    path('lenders/<int:lender_id>/delete/', LenderDeleteView.as_view(), name='lender_delete'),
]
