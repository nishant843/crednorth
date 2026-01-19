from django.urls import path
from .views import HealthCheckView, DedupeAdminView
from .views_admin import BulkDedupeAPIView

urlpatterns = [
    path('health/', HealthCheckView.as_view()),
    path('admin/bulk-dedupe/', BulkDedupeAPIView.as_view()),
]
