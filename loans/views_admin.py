import os
import tempfile
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import FileResponse
from .services.bulk_processor import process_csv


class BulkDedupeAPIView(APIView):
    def post(self, request):
        uploaded_file = request.FILES.get('file')
        lenders = request.POST.getlist('lenders')
        check_dedupe = request.POST.get('check_dedupe', 'false').lower() == 'true'
        send_leads = request.POST.get('send_leads', 'false').lower() == 'true'
        
        if not uploaded_file:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not lenders:
            return Response(
                {'error': 'No lenders selected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        input_fd, input_path = tempfile.mkstemp(suffix='.csv')
        output_fd, output_path = tempfile.mkstemp(suffix='.csv')
        
        try:
            with os.fdopen(input_fd, 'wb') as input_file:
                for chunk in uploaded_file.chunks():
                    input_file.write(chunk)
            
            os.close(output_fd)
            
            try:
                process_csv(input_path, output_path, lenders, check_dedupe, send_leads)
            except ValueError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return Response(
                    {'error': 'Processing failed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            response = FileResponse(
                open(output_path, 'rb'),
                as_attachment=True,
                filename='bulk_dedupe_results.csv'
            )
            
            return response
            
        except Exception as e:
            return Response(
                {'error': 'File processing failed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        finally:
            if os.path.exists(input_path):
                try:
                    os.unlink(input_path)
                except:
                    pass
