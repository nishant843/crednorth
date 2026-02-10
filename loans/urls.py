from django.urls import path
from .views import DedupeAdminView
from .views_admin import (
    BulkDedupeAPIView, 
    CRMDashboardView,
    LeadCreateView,
    LeadUpdateView,
    LeadDeleteView,
    DisbursalCreateView,
    DisbursalDeleteView,
    LenderCreateView,
    CSVValidateView,
    BulkUploadView
)

urlpatterns = [
    path('admin/bulk-dedupe/', BulkDedupeAPIView.as_view()),
    path('admin-crm-dashboard/', CRMDashboardView.as_view(), name='crm_dashboard'),
    path('leads/create/', LeadCreateView.as_view(), name='lead_create'),
    path('leads/<int:lead_id>/update/', LeadUpdateView.as_view(), name='lead_update'),
    path('leads/<int:lead_id>/delete/', LeadDeleteView.as_view(), name='lead_delete'),
    path('leads/validate-csv/', CSVValidateView.as_view(), name='csv_validate'),
    path('leads/bulk-upload/', BulkUploadView.as_view(), name='bulk_upload'),
    path('disbursals/create/', DisbursalCreateView.as_view(), name='disbursal_create'),
    path('disbursals/<int:disbursal_id>/delete/', DisbursalDeleteView.as_view(), name='disbursal_delete'),
    path('lenders/create/', LenderCreateView.as_view(), name='lender_create'),
]
