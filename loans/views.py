from django.shortcuts import render
from django.views import View
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import os


class HealthCheckView(APIView):
    def get(self, request):
        return Response(
            {"status": "Backend is running"},
            status=status.HTTP_200_OK
        )


class DedupeAdminView(View):
    def get(self, request):
    # Render template from configured TEMPLATE_DIRS (place dedupe_admin.html in your project templates/)
        return render(request, 'dedupe_admin.html')
