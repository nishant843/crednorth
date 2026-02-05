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
    LenderCreateView
)

urlpatterns = [
    path('admin/bulk-dedupe/', BulkDedupeAPIView.as_view()),
    path('admin-crm-dashboard/', CRMDashboardView.as_view(), name='crm_dashboard'),
    path('api/leads/create/', LeadCreateView.as_view(), name='lead_create'),
    path('api/leads/<int:lead_id>/update/', LeadUpdateView.as_view(), name='lead_update'),
    path('api/leads/<int:lead_id>/delete/', LeadDeleteView.as_view(), name='lead_delete'),
    path('api/disbursals/create/', DisbursalCreateView.as_view(), name='disbursal_create'),
    path('api/disbursals/<int:disbursal_id>/delete/', DisbursalDeleteView.as_view(), name='disbursal_delete'),
    path('api/lenders/create/', LenderCreateView.as_view(), name='lender_create'),
]
