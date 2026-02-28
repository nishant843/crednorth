from django.urls import path
from .views import DedupeAdminView
from .views_admin import (
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

urlpatterns = [
    path('admin/bulk-dedupe/', BulkDedupeAPIView.as_view()),
    path('admin-crm-dashboard/', CRMDashboardView.as_view(), name='crm_dashboard'),
    path('admin-crm-dashboard/users/', CRMDashboardView.as_view(), name='crm_users'),
    path('admin-crm-dashboard/lenders/', CRMLendersView.as_view(), name='crm_lenders'),
    path('admin-crm-dashboard/disbursals/', CRMDisbursalsView.as_view(), name='crm_disbursals'),
    path('admin-crm-dashboard/fetch-data/', CRMFetchDataView.as_view(), name='crm_fetch_data'),
    path('leads/validate-csv/', CSVValidateView.as_view(), name='csv_validate'),
    path('leads/bulk-upload/', BulkUploadView.as_view(), name='bulk_upload'),
    path('leads/export/', ExportLeadsView.as_view(), name='export_leads'),
    path('leads/<int:lead_id>/', LeadDetailView.as_view(), name='lead_detail'),
    path('leads/<int:lead_id>/update/', LeadUpdateView.as_view(), name='lead_update'),
    path('leads/<int:lead_id>/delete/', LeadDeleteView.as_view(), name='lead_delete'),
    path('disbursals/create/', DisbursalCreateView.as_view(), name='disbursal_create'),
    path('disbursals/<int:disbursal_id>/delete/', DisbursalDeleteView.as_view(), name='disbursal_delete'),
    path('lenders/create/', LenderCreateView.as_view(), name='lender_create'),
]
