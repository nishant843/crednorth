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
        # Get the path to the HTML file
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        html_path = os.path.join(base_dir, 'dedupe_admin.html')
        
        with open(html_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
        
        from django.http import HttpResponse
        return HttpResponse(html_content)
