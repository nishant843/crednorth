import os
import tempfile
import csv
import uuid
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import FileResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q
from django.core.cache import cache
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


class CSVValidateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Validate CSV file for bulk upload"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request):
        uploaded_file = request.FILES.get('file')
        lender_id = request.POST.get('lender')
        
        if not uploaded_file:
            return JsonResponse({'success': False, 'error': 'No file provided'}, status=400)
        
        if not lender_id:
            return JsonResponse({'success': False, 'error': 'No lender selected'}, status=400)
        
        try:
            lender = get_object_or_404(Lender, id=lender_id)
        except:
            return JsonResponse({'success': False, 'error': 'Invalid lender'}, status=400)
        
        try:
            # Read and decode CSV
            try:
                decoded_file = uploaded_file.read().decode('utf-8').splitlines()
            except UnicodeDecodeError:
                # Try with different encoding
                uploaded_file.seek(0)
                decoded_file = uploaded_file.read().decode('utf-8-sig').splitlines()
            
            csv_reader = csv.DictReader(decoded_file)
            
            # Expected columns
            required_columns = ['first_name', 'last_name', 'phoneNumber', 'pan', 'pinCode', 'income', 'employmentType']
            optional_columns = ['dob', 'gender']
            
            # Check if required columns exist
            if not csv_reader.fieldnames:
                return JsonResponse({'success': False, 'error': 'CSV file is empty'}, status=400)
            
            missing_columns = [col for col in required_columns if col not in csv_reader.fieldnames]
            if missing_columns:
                return JsonResponse({
                    'success': False,
                    'error': f'Missing required columns: {", ".join(missing_columns)}'
                }, status=400)
            
            # Validate rows
            valid_rows = []
            errors = []
            row_number = 1
            
            # Get existing phone numbers and PANs for duplicate checking
            existing_phones = set(Lead.objects.values_list('phone_number', flat=True))
            existing_pans = set(Lead.objects.values_list('pan', flat=True))
            
            # Track duplicates within the CSV itself
            csv_phones = set()
            csv_pans = set()
            
            for row in csv_reader:
                row_number += 1
                row_errors = []
                row_warnings = []
                
                # Check required fields are not empty
                if not row.get('first_name', '').strip():
                    row_errors.append(f'Row {row_number}: Missing first_name - SKIPPED')
                    errors.extend(row_errors)
                    continue
                if not row.get('last_name', '').strip():
                    row_errors.append(f'Row {row_number}: Missing last_name - SKIPPED')
                    errors.extend(row_errors)
                    continue
                if not row.get('phoneNumber', '').strip():
                    row_errors.append(f'Row {row_number}: Missing phoneNumber - SKIPPED')
                    errors.extend(row_errors)
                    continue
                if not row.get('pan', '').strip():
                    row_errors.append(f'Row {row_number}: Missing pan - SKIPPED')
                    errors.extend(row_errors)
                    continue
                if not row.get('pinCode', '').strip():
                    row_errors.append(f'Row {row_number}: Missing pinCode - SKIPPED')
                    errors.extend(row_errors)
                    continue
                if not row.get('income', '').strip():
                    row_errors.append(f'Row {row_number}: Missing income - SKIPPED')
                    errors.extend(row_errors)
                    continue
                if not row.get('employmentType', '').strip():
                    row_errors.append(f'Row {row_number}: Missing employmentType - SKIPPED')
                    errors.extend(row_errors)
                    continue
                
                # Get phone and PAN for duplicate checking
                phone = row['phoneNumber'].strip()
                pan = row['pan'].strip().upper()
                
                # Check for duplicates in database
                if phone in existing_phones:
                    row_errors.append(f'Row {row_number}: Phone number {phone} already exists in database - SKIPPED')
                    errors.extend(row_errors)
                    continue
                
                if pan in existing_pans:
                    row_errors.append(f'Row {row_number}: PAN {pan} already exists in database - SKIPPED')
                    errors.extend(row_errors)
                    continue
                
                # Check for duplicates within the CSV
                if phone in csv_phones:
                    row_errors.append(f'Row {row_number}: Duplicate phone number {phone} in CSV - SKIPPED')
                    errors.extend(row_errors)
                    continue
                
                if pan in csv_pans:
                    row_errors.append(f'Row {row_number}: Duplicate PAN {pan} in CSV - SKIPPED')
                    errors.extend(row_errors)
                    continue
                
                # Validate data types
                try:
                    if row.get('income', '').strip():
                        float(row['income'])
                except ValueError:
                    row_warnings.append(f'Row {row_number}: Invalid income value')
                
                # Validate PAN format (basic validation)
                if pan and len(pan) != 10:
                    row_warnings.append(f'Row {row_number}: PAN should be 10 characters (found {len(pan)})')
                
                # Validate DOB format if provided
                dob = row.get('dob', '').strip()
                if dob:
                    try:
                        datetime.strptime(dob, '%Y-%m-%d')
                    except ValueError:
                        row_warnings.append(f'Row {row_number}: Invalid date format for dob (expected YYYY-MM-DD), will be ignored')
                        dob = None
                
                # Add warnings to errors list but still process the row
                if row_warnings:
                    errors.extend(row_warnings)
                
                # Track phone and PAN to check for duplicates within CSV
                csv_phones.add(phone)
                csv_pans.add(pan)
                
                # Add row to valid rows
                valid_rows.append({
                    'first_name': row['first_name'].strip(),
                    'last_name': row['last_name'].strip(),
                    'phone_number': phone,
                    'pan': pan,
                    'dob': dob if dob else None,
                    'gender': row.get('gender', '').strip() or '',
                    'pin_code': row['pinCode'].strip(),
                    'income': row['income'].strip(),
                    'employment_type': row['employmentType'].strip(),
                    'lender_id': lender_id
                })
            
            if not valid_rows:
                return JsonResponse({
                    'success': False,
                    'error': 'No valid rows found in CSV',
                    'errors': errors
                }, status=400)
            
            # Generate session ID to store data temporarily
            session_id = str(uuid.uuid4())
            
            # Store validated data in cache (expires in 1 hour)
            cache.set(f'bulk_upload_{session_id}', {
                'rows': valid_rows,
                'lender_id': lender_id,
                'lender_name': lender.name
            }, 3600)
            
            # Return success with preview data
            return JsonResponse({
                'success': True,
                'session_id': session_id,
                'total_rows': len(valid_rows),
                'lender_name': lender.name,
                'preview_rows': valid_rows[:10],  # First 10 rows for preview
                'errors': errors[:20] if errors else []  # First 20 errors if any
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error processing CSV: {str(e)}'
            }, status=400)


class BulkUploadView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Bulk upload validated leads to database"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request):
        session_id = request.POST.get('session_id')
        
        if not session_id:
            return JsonResponse({'success': False, 'error': 'No session ID provided'}, status=400)
        
        # Retrieve validated data from cache
        cached_data = cache.get(f'bulk_upload_{session_id}')
        
        if not cached_data:
            return JsonResponse({
                'success': False,
                'error': 'Session expired or invalid. Please upload the CSV again.'
            }, status=400)
        
        try:
            rows = cached_data['rows']
            lender_id = cached_data['lender_id']
            lender = get_object_or_404(Lender, id=lender_id)
            
            # Double-check for duplicates before insertion (in case new leads were added)
            existing_phones = set(Lead.objects.values_list('phone_number', flat=True))
            existing_pans = set(Lead.objects.values_list('pan', flat=True))
            
            # Bulk create leads (skip duplicates)
            leads_to_create = []
            skipped_count = 0
            
            for row in rows:
                # Skip if duplicate found
                if row['phone_number'] in existing_phones or row['pan'] in existing_pans:
                    skipped_count += 1
                    continue
                
                leads_to_create.append(Lead(
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    phone_number=row['phone_number'],
                    pan=row['pan'],
                    dob=row['dob'],
                    gender=row['gender'],
                    pin_code=row['pin_code'],
                    income=row['income'],
                    employment_type=row['employment_type'],
                    lender=lender,
                    status='pending'
                ))
                
                # Add to existing sets to prevent duplicates within this batch
                existing_phones.add(row['phone_number'])
                existing_pans.add(row['pan'])
            
            # Create all leads at once
            if leads_to_create:
                created_leads = Lead.objects.bulk_create(leads_to_create)
            else:
                created_leads = []
            
            # Clear cache
            cache.delete(f'bulk_upload_{session_id}')
            
            response_data = {
                'success': True,
                'created_count': len(created_leads)
            }
            
            if skipped_count > 0:
                response_data['message'] = f'Created {len(created_leads)} leads. Skipped {skipped_count} duplicates.'
            
            return JsonResponse(response_data)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error creating leads: {str(e)}'
            }, status=400)
