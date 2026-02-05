import os
import tempfile
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import FileResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q
from .services.bulk_processor import process_csv
from .models import Lead, LoanDisbursal, Lender


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


class CRMDashboardView(LoginRequiredMixin, UserPassesTestMixin, View):
    """CRM Dashboard with filtering and statistics"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request):
        # Get filter parameters
        lender_filter = request.GET.get('lender', '')
        
        # Base querysets
        leads_query = Lead.objects.all()
        disbursals_query = LoanDisbursal.objects.all()
        
        # Apply lender filter if specified
        if lender_filter:
            leads_query = leads_query.filter(lender__name=lender_filter)
            disbursals_query = disbursals_query.filter(lead__lender__name=lender_filter)
        
        # Calculate statistics
        total_users = User.objects.count()
        total_leads = leads_query.count()
        total_approved = leads_query.filter(status='approved').count()
        total_disbursals = disbursals_query.count()
        total_disbursed_amount = disbursals_query.aggregate(
            total=Sum('loan_amount')
        )['total'] or 0
        
        # Get all lenders for filter dropdown
        lenders = Lender.objects.all()
        
        # Get recent leads for display (paginate in production)
        recent_leads = leads_query.select_related('lender')[:50]
        
        # Get recent disbursals
        recent_disbursals = disbursals_query.select_related('lead', 'lead__lender')[:50]
        
        context = {
            'total_users': total_users,
            'total_leads': total_leads,
            'total_approved': total_approved,
            'total_disbursals': total_disbursals,
            'total_disbursed_amount': total_disbursed_amount,
            'lenders': lenders,
            'selected_lender': lender_filter,
            'recent_leads': recent_leads,
            'recent_disbursals': recent_disbursals,
        }
        
        return render(request, 'crm_dashboard.html', context)


class LeadCreateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Create a new lead"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request):
        try:
            lender_id = request.POST.get('lender')
            lender = get_object_or_404(Lender, id=lender_id)
            
            lead = Lead.objects.create(
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                phone_number=request.POST.get('phone_number'),
                pan=request.POST.get('pan'),
                dob=request.POST.get('dob') if request.POST.get('dob') else None,
                gender=request.POST.get('gender', ''),
                pin_code=request.POST.get('pin_code'),
                income=request.POST.get('income'),
                employment_type=request.POST.get('employment_type'),
                lender=lender,
                status=request.POST.get('status', 'pending')
            )
            
            return JsonResponse({'success': True, 'lead_id': lead.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class LeadUpdateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Update an existing lead"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request, lead_id):
        try:
            lead = get_object_or_404(Lead, id=lead_id)
            
            if request.POST.get('lender'):
                lender = get_object_or_404(Lender, id=request.POST.get('lender'))
                lead.lender = lender
            
            lead.first_name = request.POST.get('first_name', lead.first_name)
            lead.last_name = request.POST.get('last_name', lead.last_name)
            lead.phone_number = request.POST.get('phone_number', lead.phone_number)
            lead.pan = request.POST.get('pan', lead.pan)
            
            if request.POST.get('dob'):
                lead.dob = request.POST.get('dob')
            
            lead.gender = request.POST.get('gender', lead.gender)
            lead.pin_code = request.POST.get('pin_code', lead.pin_code)
            lead.income = request.POST.get('income', lead.income)
            lead.employment_type = request.POST.get('employment_type', lead.employment_type)
            lead.status = request.POST.get('status', lead.status)
            
            lead.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class LeadDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Delete a lead"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request, lead_id):
        try:
            lead = get_object_or_404(Lead, id=lead_id)
            lead.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class DisbursalCreateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Create a new loan disbursal"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request):
        try:
            lead_id = request.POST.get('lead')
            lead = get_object_or_404(Lead, id=lead_id)
            
            disbursal = LoanDisbursal.objects.create(
                lead=lead,
                loan_amount=request.POST.get('loan_amount'),
                disbursed_date=request.POST.get('disbursed_date'),
                interest_rate=request.POST.get('interest_rate') if request.POST.get('interest_rate') else None,
                tenure_months=request.POST.get('tenure_months') if request.POST.get('tenure_months') else None
            )
            
            return JsonResponse({'success': True, 'disbursal_id': disbursal.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class DisbursalDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Delete a loan disbursal"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request, disbursal_id):
        try:
            disbursal = get_object_or_404(LoanDisbursal, id=disbursal_id)
            disbursal.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class LenderCreateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Create a new lender"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request):
        try:
            lender = Lender.objects.create(
                name=request.POST.get('name'),
                contact_email=request.POST.get('contact_email', ''),
                contact_phone=request.POST.get('contact_phone', '')
            )
            
            return JsonResponse({'success': True, 'lender_id': lender.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
