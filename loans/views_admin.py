import os
import tempfile
import csv
import uuid
import io
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import FileResponse, JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Sum, Count, Q
from django.core.cache import cache
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .services.bulk_processor import process_csv
from .models import Lead, LoanDisbursal, Lender
from users.models import User


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
    """
    CRM Dashboard for Leads management.
    Leads are PRIMARY - CSV uploads create Leads → auto-generate Users.
    """
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request):
        # Get filter parameters
        status_filter = request.GET.get('status', '')
        profession_filter = request.GET.get('profession', '')
        gender_filter = request.GET.get('gender', '')
        income_min = request.GET.get('income_min', '')
        income_max = request.GET.get('income_max', '')
        pin_code_filter = request.GET.get('pin_code', '')
        search_query = request.GET.get('search', '')
        active_tab = request.GET.get('tab', 'overview')  # Get active tab from query params
        page = request.GET.get('page', 1)  # Get page number for pagination
        
        # New inline filter parameters
        name_filter = request.GET.get('name', '')
        phone_filter = request.GET.get('phone', '')
        pan_filter = request.GET.get('pan', '')
        email_filter = request.GET.get('email', '')
        age_min = request.GET.get('age_min', '')
        age_max = request.GET.get('age_max', '')
        city_filter = request.GET.get('city', '')
        state_filter = request.GET.get('state', '')
        bureau_min = request.GET.get('bureau_min', '')
        bureau_max = request.GET.get('bureau_max', '')
        
        # If any filters are applied, automatically switch to leads tab or show users page
        has_filters = any([
            status_filter, profession_filter, gender_filter, income_min, income_max,
            pin_code_filter, search_query, name_filter, phone_filter, pan_filter,
            email_filter, age_min, age_max, city_filter, state_filter, bureau_min, bureau_max
        ])
        
        # Auto-switch to leads tab if filters are active and no explicit tab is set
        if has_filters and active_tab == 'overview':
            active_tab = 'leads'
        
        # Determine active_page based on URL path first, then filters
        if '/users/' in request.path:
            active_page = 'users'
        elif has_filters:
            active_page = 'users'
        else:
            active_page = 'overview'
        
        # Base querysets - Leads are primary
        leads_query = Lead.objects.all()
        disbursals_query = LoanDisbursal.objects.all()
        
        # Apply filters to leads
        if status_filter:
            leads_query = leads_query.filter(status=status_filter)
        
        if profession_filter:
            leads_query = leads_query.filter(profession__icontains=profession_filter)
        
        if gender_filter:
            leads_query = leads_query.filter(gender__iexact=gender_filter)
        
        if income_min:
            try:
                leads_query = leads_query.filter(monthly_income__gte=float(income_min))
            except ValueError:
                pass
        
        if income_max:
            try:
                leads_query = leads_query.filter(monthly_income__lte=float(income_max))
            except ValueError:
                pass
        
        if pin_code_filter:
            leads_query = leads_query.filter(pin_code__icontains=pin_code_filter)
        
        if search_query:
            leads_query = leads_query.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(phone_number__icontains=search_query) |
                Q(pan_number__icontains=search_query) |
                Q(email__icontains=search_query)
            )
        
        # Apply new inline filters
        if name_filter:
            leads_query = leads_query.filter(
                Q(first_name__icontains=name_filter) |
                Q(last_name__icontains=name_filter)
            )
        
        if phone_filter:
            leads_query = leads_query.filter(phone_number__icontains=phone_filter)
        
        if pan_filter:
            leads_query = leads_query.filter(pan_number__icontains=pan_filter)
        
        if email_filter:
            leads_query = leads_query.filter(email__icontains=email_filter)
        
        if city_filter:
            leads_query = leads_query.filter(city__icontains=city_filter)
        
        if state_filter:
            leads_query = leads_query.filter(state__icontains=state_filter)
        
        if age_min:
            try:
                leads_query = leads_query.filter(age__gte=int(age_min))
            except ValueError:
                pass
        
        if age_max:
            try:
                leads_query = leads_query.filter(age__lte=int(age_max))
            except ValueError:
                pass
        
        if bureau_min:
            try:
                leads_query = leads_query.filter(bureau_score__gte=int(bureau_min))
            except ValueError:
                pass
        
        if bureau_max:
            try:
                leads_query = leads_query.filter(bureau_score__lte=int(bureau_max))
            except ValueError:
                pass
        
        # Calculate statistics
        total_leads = leads_query.count()
        leads_with_consent = leads_query.filter(consent_taken=True).count()
        high_bureau_leads = leads_query.filter(bureau_score__gte=750).count()
        total_pending = leads_query.filter(status='pending').count()
        total_approved = leads_query.filter(status='approved').count()
        total_rejected = leads_query.filter(status='rejected').count()
        total_disbursals = disbursals_query.count()
        total_disbursed_amount = disbursals_query.aggregate(
            total=Sum('loan_amount')
        )['total'] or 0
        
        # Get all lenders (kept for potential future use with applications)
        lenders = Lender.objects.all()
        
        # Get unique values for filters
        professions_raw = Lead.objects.exclude(profession='').values_list('profession', flat=True).distinct()
        professions = sorted(set([prof for prof in professions_raw if prof]))
        
        genders_raw = Lead.objects.exclude(gender='').values_list('gender', flat=True).distinct()
        genders = sorted(set([gender for gender in genders_raw if gender]))
        
        # Get all leads for display with User and UserMeta data
        from users.models import User, UserMeta
        all_leads_query = leads_query.order_by('-created_at')
        
        # Implement pagination - 50 leads per page
        paginator = Paginator(all_leads_query, 50)
        
        try:
            leads_page = paginator.page(page)
        except PageNotAnInteger:
            leads_page = paginator.page(1)
        except EmptyPage:
            leads_page = paginator.page(paginator.num_pages)
        
        # Enrich leads with User and UserMeta data
        enriched_leads = []
        for lead in leads_page:
            try:
                user = User.objects.get(phone_number=lead.phone_number)
                try:
                    user_meta = user.meta
                except UserMeta.DoesNotExist:
                    user_meta = None
                lead.user_data = user
                lead.user_meta = user_meta
            except User.DoesNotExist:
                lead.user_data = None
                lead.user_meta = None
            enriched_leads.append(lead)
        
        # Get all disbursals
        all_disbursals = disbursals_query.select_related('lead').order_by('-disbursed_date')
        
        # Calculate user stats for overview
        total_users = User.objects.count()
        users_with_consent = leads_query.filter(consent_taken=True).count()
        high_bureau_users = leads_query.filter(bureau_score__gte=750).count()
        
        context = {
            'total_leads': total_leads,
            'leads_with_consent': leads_with_consent,
            'high_bureau_leads': high_bureau_leads,
            'total_pending': total_pending,
            'total_approved': total_approved,
            'total_rejected': total_rejected,
            'total_disbursals': total_disbursals,
            'total_disbursed_amount': total_disbursed_amount,
            'lenders': lenders,
            'professions': professions,
            'genders': genders,
            'selected_status': status_filter,
            'selected_profession': profession_filter,
            'selected_gender': gender_filter,
            'income_min': income_min,
            'income_max': income_max,
            'pin_code': pin_code_filter,
            'search_query': search_query,
            'age_min': age_min,
            'age_max': age_max,
            'bureau_min': bureau_min,
            'bureau_max': bureau_max,
            # Inline filter parameters
            'name_filter': name_filter,
            'phone_filter': phone_filter,
            'pan_filter': pan_filter,
            'email_filter': email_filter,
            'city_filter': city_filter,
            'state_filter': state_filter,
            'all_leads': enriched_leads,
            'all_disbursals': all_disbursals,
            'total_users': total_users,
            'users_with_consent': users_with_consent,
            'high_bureau_users': high_bureau_users,
            # Pagination
            'leads_page': leads_page,
            'active_tab': active_tab,
            'active_page': active_page,
        }
        
        return render(request, 'crm_dashboard.html', context)
    
    def post(self, request):
        """Handle bulk Lead CSV upload - Leads auto-create Users"""
        uploaded_file = request.FILES.get('lead_csv_file')
        
        if not uploaded_file:
            messages.error(request, 'Please select a CSV file to upload.')
            return redirect('crm_dashboard')
        
        # Validate file extension
        if not uploaded_file.name.endswith('.csv'):
            messages.error(request, 'Invalid file type.Please upload a CSV file.')
            return redirect('crm_dashboard')
        
        try:
            # Read the CSV file
            decoded_file = uploaded_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            csv_reader = csv.DictReader(io_string)
            
            # Convert to list for processing
            csv_data_list = list(csv_reader)
            
            if not csv_data_list:
                messages.warning(request, 'The CSV file is empty.')
                return redirect('crm_dashboard')
            
            # Process the CSV data - create Leads (which auto-create Users)
            from .services.lead_csv_processor import bulk_create_or_update_leads_from_csv
            result = bulk_create_or_update_leads_from_csv(csv_data_list)
            
            # Display results
            if result['created'] > 0 or result['updated'] > 0:
                success_msg = f"Successfully processed {result['created'] + result['updated']} leads. "
                success_msg += f"Created: {result['created']}, Updated: {result['updated']}"
                messages.success(request, success_msg)
            
            if result['failed'] > 0:
                error_msg = f"{result['failed']} leads failed to process."
                if result['errors']:
                    # Show first 3 errors
                    error_details = '<br>'.join(result['errors'][:3])
                    if len(result['errors']) > 3:
                        error_details += f"<br>... and {len(result['errors']) - 3} more errors"
                    messages.error(request, f"{error_msg}<br>{error_details}")
                else:
                    messages.error(request, error_msg)
            
        except UnicodeDecodeError:
            messages.error(request, 'Unable to decode the file. Please ensure it is a valid UTF-8 encoded CSV file.')
        except Exception as e:
            messages.error(request, f'Error processing CSV file: {str(e)}')
        
        return redirect('crm_dashboard')


class CRMLendersView(LoginRequiredMixin, UserPassesTestMixin, View):
    """CRM Lenders management page"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request):
        # Get all lenders
        lenders = Lender.objects.all()
        
        # Calculate overview statistics (for consistency)
        leads_query = Lead.objects.all()
        disbursals_query = LoanDisbursal.objects.all()
        
        total_leads = leads_query.count()
        leads_with_consent = leads_query.filter(consent_taken=True).count()
        high_bureau_leads = leads_query.filter(bureau_score__gte=750).count()
        total_pending = leads_query.filter(status='pending').count()
        total_approved = leads_query.filter(status='approved').count()
        total_rejected = leads_query.filter(status='rejected').count()
        total_disbursals = disbursals_query.count()
        total_disbursed_amount = disbursals_query.aggregate(
            total=Sum('loan_amount')
        )['total'] or 0
        
        total_users = User.objects.count()
        users_with_consent = leads_query.filter(consent_taken=True).count()
        high_bureau_users = leads_query.filter(bureau_score__gte=750).count()
        
        context = {
            'total_leads': total_leads,
            'leads_with_consent': leads_with_consent,
            'high_bureau_leads': high_bureau_leads,
            'total_pending': total_pending,
            'total_approved': total_approved,
            'total_rejected': total_rejected,
            'total_disbursals': total_disbursals,
            'total_disbursed_amount': total_disbursed_amount,
            'lenders': lenders,
            'total_users': total_users,
            'users_with_consent': users_with_consent,
            'high_bureau_users': high_bureau_users,
            'active_page': 'lenders',
        }
        
        return render(request, 'crm_dashboard.html', context)


class CRMDisbursalsView(LoginRequiredMixin, UserPassesTestMixin, View):
    """CRM Disbursals management page"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request):
        # Get all disbursals
        disbursals_query = LoanDisbursal.objects.all()
        all_disbursals = disbursals_query.select_related('lead').order_by('-disbursed_date')
        
        # Calculate overview statistics (for consistency)
        leads_query = Lead.objects.all()
        
        total_leads = leads_query.count()
        leads_with_consent = leads_query.filter(consent_taken=True).count()
        high_bureau_leads = leads_query.filter(bureau_score__gte=750).count()
        total_pending = leads_query.filter(status='pending').count()
        total_approved = leads_query.filter(status='approved').count()
        total_rejected = leads_query.filter(status='rejected').count()
        total_disbursals = disbursals_query.count()
        total_disbursed_amount = disbursals_query.aggregate(
            total=Sum('loan_amount')
        )['total'] or 0
        
        total_users = User.objects.count()
        users_with_consent = leads_query.filter(consent_taken=True).count()
        high_bureau_users = leads_query.filter(bureau_score__gte=750).count()
        
        lenders = Lender.objects.all()
        
        context = {
            'total_leads': total_leads,
            'leads_with_consent': leads_with_consent,
            'high_bureau_leads': high_bureau_leads,
            'total_pending': total_pending,
            'total_approved': total_approved,
            'total_rejected': total_rejected,
            'total_disbursals': total_disbursals,
            'total_disbursed_amount': total_disbursed_amount,
            'all_disbursals': all_disbursals,
            'lenders': lenders,
            'total_users': total_users,
            'users_with_consent': users_with_consent,
            'high_bureau_users': high_bureau_users,
            'active_page': 'disbursals',
        }
        
        return render(request, 'crm_dashboard.html', context)


class CRMFetchDataView(LoginRequiredMixin, UserPassesTestMixin, View):
    """CRM Fetch Data page - Upload CSV with phone numbers, download CSV with all user data"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request):
        # Get statistics for display
        leads_query = Lead.objects.all()
        disbursals_query = LoanDisbursal.objects.all()
        
        total_leads = leads_query.count()
        leads_with_consent = leads_query.filter(consent_taken=True).count()
        high_bureau_leads = leads_query.filter(bureau_score__gte=750).count()
        total_pending = leads_query.filter(status='pending').count()
        total_approved = leads_query.filter(status='approved').count()
        total_rejected = leads_query.filter(status='rejected').count()
        total_disbursals = disbursals_query.count()
        total_disbursed_amount = disbursals_query.aggregate(
            total=Sum('loan_amount')
        )['total'] or 0
        
        total_users = User.objects.count()
        users_with_consent = leads_query.filter(consent_taken=True).count()
        high_bureau_users = leads_query.filter(bureau_score__gte=750).count()
        
        lenders = Lender.objects.all()
        
        context = {
            'total_leads': total_leads,
            'leads_with_consent': leads_with_consent,
            'high_bureau_leads': high_bureau_leads,
            'total_pending': total_pending,
            'total_approved': total_approved,
            'total_rejected': total_rejected,
            'total_disbursals': total_disbursals,
            'total_disbursed_amount': total_disbursed_amount,
            'lenders': lenders,
            'total_users': total_users,
            'users_with_consent': users_with_consent,
            'high_bureau_users': high_bureau_users,
            'active_page': 'fetch_data',
        }
        
        return render(request, 'crm_dashboard.html', context)
    
    def post(self, request):
        """Handle CSV upload with phone numbers and return CSV with all user data"""
        uploaded_file = request.FILES.get('phone_csv_file')
        
        if not uploaded_file:
            return JsonResponse({'success': False, 'error': 'No file uploaded'}, status=400)
        
        if not uploaded_file.name.endswith('.csv'):
            return JsonResponse({'success': False, 'error': 'Invalid file type. Please upload a CSV file.'}, status=400)
        
        try:
            # Read the CSV file
            decoded_file = uploaded_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            csv_reader = csv.reader(io_string)
            
            # Extract phone numbers (assuming first column or column named 'phone' or 'phone_number')
            phone_numbers = []
            header = next(csv_reader, None)
            
            # Check if header exists and find phone column
            phone_col_index = 0
            if header:
                header_lower = [h.lower().strip() for h in header]
                if 'phone' in header_lower:
                    phone_col_index = header_lower.index('phone')
                elif 'phone_number' in header_lower:
                    phone_col_index = header_lower.index('phone_number')
                elif 'mobile' in header_lower:
                    phone_col_index = header_lower.index('mobile')
            
            # Extract phone numbers
            for row in csv_reader:
                if row and len(row) > phone_col_index:
                    phone = row[phone_col_index].strip()
                    if phone and phone.isdigit():
                        phone_numbers.append(phone)
            
            if not phone_numbers:
                return JsonResponse({'success': False, 'error': 'No valid phone numbers found in CSV'}, status=400)
            
            # Fetch all leads matching these phone numbers
            leads = Lead.objects.filter(phone_number__in=phone_numbers).select_related()
            
            # Create response CSV
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="user_data_export.csv"'
            
            writer = csv.writer(response)
            # Write header with all available fields
            writer.writerow([
                'ID', 'First Name', 'Last Name', 'Phone Number', 'Email', 'PAN Number',
                'Date of Birth', 'Age', 'Gender', 'City', 'State', 'Pin Code',
                'Profession', 'Monthly Income', 'Bureau Score', 'Consent Taken',
                'Status', 'Created At', 'Updated At'
            ])
            
            # Write data rows
            found_phones = set()
            for lead in leads:
                found_phones.add(lead.phone_number)
                writer.writerow([
                    lead.id,
                    lead.first_name,
                    lead.last_name,
                    lead.phone_number,
                    lead.email or '',
                    lead.pan_number,
                    lead.date_of_birth.strftime('%Y-%m-%d') if lead.date_of_birth else '',
                    lead.age or '',
                    lead.gender,
                    lead.city,
                    lead.state,
                    lead.pin_code,
                    lead.profession,
                    lead.monthly_income or '',
                    lead.bureau_score or '',
                    'Yes' if lead.consent_taken else 'No',
                    lead.status,
                    lead.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    lead.updated_at.strftime('%Y-%m-%d %H:%M:%S')
                ])
            
            # Add rows for phone numbers not found
            not_found = set(phone_numbers) - found_phones
            for phone in not_found:
                writer.writerow([
                    '', '', '', phone, '', '', '', '', '', '', '', '', '', '', '', '', 'NOT FOUND', '', ''
                ])
            
            return response
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error processing file: {str(e)}'}, status=400)


class DisbursalCreateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Create a new loan disbursal for a lead"""
    
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
        
        if not uploaded_file:
            return JsonResponse({'success': False, 'error': 'No file provided'}, status=400)
        
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
            required_columns = ['first_name', 'last_name', 'phone_number', 'pan_number', 'pin_code', 'monthly_income', 'profession']
            optional_columns = ['date_of_birth', 'gender', 'email', 'city', 'state', 'bureau_score']
            
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
            existing_pans = set(Lead.objects.values_list('pan_number', flat=True))
            
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
                if not row.get('phone_number', '').strip():
                    row_errors.append(f'Row {row_number}: Missing phone_number - SKIPPED')
                    errors.extend(row_errors)
                    continue
                if not row.get('pan_number', '').strip():
                    row_errors.append(f'Row {row_number}: Missing pan_number - SKIPPED')
                    errors.extend(row_errors)
                    continue
                if not row.get('pin_code', '').strip():
                    row_errors.append(f'Row {row_number}: Missing pin_code - SKIPPED')
                    errors.extend(row_errors)
                    continue
                if not row.get('monthly_income', '').strip():
                    row_errors.append(f'Row {row_number}: Missing monthly_income - SKIPPED')
                    errors.extend(row_errors)
                    continue
                if not row.get('profession', '').strip():
                    row_errors.append(f'Row {row_number}: Missing profession - SKIPPED')
                    errors.extend(row_errors)
                    continue
                
                # Get phone and PAN for duplicate checking
                phone = row['phone_number'].strip()
                pan = row['pan_number'].strip().upper()
                
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
                    if row.get('monthly_income', '').strip():
                        float(row['monthly_income'])
                except ValueError:
                    row_warnings.append(f'Row {row_number}: Invalid monthly_income value')
                
                # Validate PAN format (basic validation)
                if pan and len(pan) != 10:
                    row_warnings.append(f'Row {row_number}: PAN should be 10 characters (found {len(pan)})')
                
                # Validate date_of_birth format if provided
                date_of_birth = row.get('date_of_birth', '').strip()
                if date_of_birth:
                    try:
                        datetime.strptime(date_of_birth, '%Y-%m-%d')
                    except ValueError:
                        row_warnings.append(f'Row {row_number}: Invalid date format for date_of_birth (expected YYYY-MM-DD), will be ignored')
                        date_of_birth = None
                
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
                    'pan_number': pan,
                    'date_of_birth': date_of_birth if date_of_birth else None,
                    'gender': row.get('gender', '').strip() or '',
                    'email': row.get('email', '').strip() or '',
                    'city': row.get('city', '').strip() or '',
                    'state': row.get('state', '').strip() or '',
                    'pin_code': row['pin_code'].strip(),
                    'monthly_income': row['monthly_income'].strip(),
                    'profession': row['profession'].strip(),
                    'bureau_score': row.get('bureau_score', '').strip() or None
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
                'rows': valid_rows
            }, 3600)
            
            # Return success with preview data
            return JsonResponse({
                'success': True,
                'session_id': session_id,
                'total_rows': len(valid_rows),
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
            
            # Double-check for duplicates before insertion (in case new leads were added)
            existing_phones = set(Lead.objects.values_list('phone_number', flat=True))
            existing_pans = set(Lead.objects.values_list('pan_number', flat=True))
            
            # Bulk create leads (skip duplicates)
            leads_to_create = []
            skipped_count = 0
            
            for row in rows:
                # Skip if duplicate found
                if row['phone_number'] in existing_phones or row['pan_number'] in existing_pans:
                    skipped_count += 1
                    continue
                
                leads_to_create.append(Lead(
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    phone_number=row['phone_number'],
                    pan_number=row['pan_number'],
                    date_of_birth=row['date_of_birth'],
                    gender=row['gender'],
                    email=row['email'],
                    city=row['city'],
                    state=row['state'],
                    pin_code=row['pin_code'],
                    monthly_income=row['monthly_income'],
                    profession=row['profession'],
                    bureau_score=row['bureau_score'],
                    status='pending'
                ))
                
                # Add to existing sets to prevent duplicates within this batch
                existing_phones.add(row['phone_number'])
                existing_pans.add(row['pan_number'])
            
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


class ExportLeadsView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Export filtered leads to CSV"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request):
        # Get filter parameters (same as CRMDashboardView)
        status_filter = request.GET.get('status', '')
        profession_filter = request.GET.get('profession', '')
        gender_filter = request.GET.get('gender', '')
        income_min = request.GET.get('income_min', '')
        income_max = request.GET.get('income_max', '')
        pin_code_filter = request.GET.get('pin_code', '')
        search_query = request.GET.get('search', '')
        
        # New inline filter parameters
        name_filter = request.GET.get('name', '')
        phone_filter = request.GET.get('phone', '')
        pan_filter = request.GET.get('pan', '')
        email_filter = request.GET.get('email', '')
        age_min = request.GET.get('age_min', '')
        age_max = request.GET.get('age_max', '')
        city_filter = request.GET.get('city', '')
        state_filter = request.GET.get('state', '')
        bureau_min = request.GET.get('bureau_min', '')
        bureau_max = request.GET.get('bureau_max', '')
        
        # Build query
        leads_query = Lead.objects.all()
        
        # Apply filters
        if status_filter:
            leads_query = leads_query.filter(status=status_filter)
        
        if profession_filter:
            leads_query = leads_query.filter(profession__icontains=profession_filter)
        
        if gender_filter:
            leads_query = leads_query.filter(gender__iexact=gender_filter)
        
        if income_min:
            try:
                leads_query = leads_query.filter(monthly_income__gte=float(income_min))
            except ValueError:
                pass
        
        if income_max:
            try:
                leads_query = leads_query.filter(monthly_income__lte=float(income_max))
            except ValueError:
                pass
        
        if pin_code_filter:
            leads_query = leads_query.filter(pin_code__icontains=pin_code_filter)
        
        if search_query:
            leads_query = leads_query.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(phone_number__icontains=search_query) |
                Q(pan_number__icontains=search_query) |
                Q(email__icontains=search_query)
            )
        
        # Apply new inline filters
        if name_filter:
            leads_query = leads_query.filter(
                Q(first_name__icontains=name_filter) |
                Q(last_name__icontains=name_filter)
            )
        
        if phone_filter:
            leads_query = leads_query.filter(phone_number__icontains=phone_filter)
        
        if pan_filter:
            leads_query = leads_query.filter(pan_number__icontains=pan_filter)
        
        if email_filter:
            leads_query = leads_query.filter(email__icontains=email_filter)
        
        if city_filter:
            leads_query = leads_query.filter(city__icontains=city_filter)
        
        if state_filter:
            leads_query = leads_query.filter(state__icontains=state_filter)
        
        if age_min:
            try:
                leads_query = leads_query.filter(age__gte=int(age_min))
            except ValueError:
                pass
        
        if age_max:
            try:
                leads_query = leads_query.filter(age__lte=int(age_max))
            except ValueError:
                pass
        
        if bureau_min:
            try:
                leads_query = leads_query.filter(bureau_score__gte=int(bureau_min))
            except ValueError:
                pass
        
        if bureau_max:
            try:
                leads_query = leads_query.filter(bureau_score__lte=int(bureau_max))
            except ValueError:
                pass
        
        # Get all matching leads
        leads = leads_query.order_by('-created_at')
        
        # Create CSV response
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="leads_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        # Write header
        writer.writerow([
            'ID', 'First Name', 'Last Name', 'Phone', 'PAN', 'Email', 'Date of Birth', 'Age', 
            'Gender', 'City', 'State', 'Pin Code', 'Profession', 'Monthly Income', 
            'Bureau Score', 'Status', 'Consent Taken', 'Created At'
        ])
        
        # Write data
        for lead in leads:
            writer.writerow([
                lead.id,
                lead.first_name,
                lead.last_name,
                lead.phone_number,
                lead.pan_number,
                lead.email or '',
                lead.date_of_birth.strftime('%Y-%m-%d') if lead.date_of_birth else '',
                lead.age or '',
                lead.gender or '',
                lead.city or '',
                lead.state or '',
                lead.pin_code,
                lead.profession or '',
                lead.monthly_income or '',
                lead.bureau_score or '',
                lead.status,
                'Yes' if lead.consent_taken else 'No',
                lead.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response


class LeadDetailView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Get lead details for profile view"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)
            
            # Get associated user and meta data
            from users.models import User, UserMeta
            user_data = None
            user_meta = None
            
            try:
                user = User.objects.get(phone_number=lead.phone_number)
                user_data = {
                    'bureau_score': user.bureau_score,
                    'income_mode': user.income_mode,
                }
                try:
                    meta = user.meta
                    user_meta = {
                        'data_source': meta.data_source,
                        'data_attribution': meta.data_attribution,
                        'first_added_date': meta.first_added_date.strftime('%Y-%m-%d'),
                        'last_updated_date': meta.last_updated_date.strftime('%Y-%m-%d'),
                    }
                except UserMeta.DoesNotExist:
                    pass
            except User.DoesNotExist:
                pass
            
            data = {
                'success': True,
                'lead': {
                    'id': lead.id,
                    'first_name': lead.first_name,
                    'last_name': lead.last_name,
                    'phone_number': lead.phone_number,
                    'email': lead.email or '',
                    'pan_number': lead.pan_number,
                    'date_of_birth': lead.date_of_birth.strftime('%Y-%m-%d') if lead.date_of_birth else '',
                    'age': lead.age,
                    'gender': lead.gender or '',
                    'city': lead.city or '',
                    'state': lead.state or '',
                    'pin_code': lead.pin_code,
                    'profession': lead.profession or '',
                    'monthly_income': str(lead.monthly_income) if lead.monthly_income else '',
                    'bureau_score': lead.bureau_score,
                    'status': lead.status,
                    'consent_taken': lead.consent_taken,
                    'created_at': lead.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'updated_at': lead.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                },
                'user_data': user_data,
                'user_meta': user_meta,
            }
            
            return JsonResponse(data)
        except Lead.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Lead not found'}, status=404)


class LeadUpdateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Update lead details"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request, lead_id):
        from django.core.exceptions import ValidationError
        try:
            lead = Lead.objects.get(id=lead_id)
            
            # Update fields from POST data
            lead.first_name = request.POST.get('first_name', lead.first_name)
            lead.last_name = request.POST.get('last_name', lead.last_name)
            lead.phone_number = request.POST.get('phone_number', lead.phone_number)
            lead.email = request.POST.get('email', lead.email)
            lead.pan_number = request.POST.get('pan_number', lead.pan_number)
            lead.gender = request.POST.get('gender', lead.gender)
            lead.city = request.POST.get('city', lead.city)
            lead.state = request.POST.get('state', lead.state)
            lead.pin_code = request.POST.get('pin_code', lead.pin_code)
            lead.profession = request.POST.get('profession', lead.profession)
            lead.status = request.POST.get('status', lead.status)
            
            # Handle date of birth
            dob = request.POST.get('date_of_birth')
            if dob:
                from datetime import datetime
                lead.date_of_birth = datetime.strptime(dob, '%Y-%m-%d').date()
            
            # Handle numeric fields
            monthly_income = request.POST.get('monthly_income')
            if monthly_income:
                lead.monthly_income = float(monthly_income)
            
            bureau_score = request.POST.get('bureau_score')
            if bureau_score:
                lead.bureau_score = int(bureau_score)
            
            # Handle consent
            consent = request.POST.get('consent_taken')
            lead.consent_taken = consent == 'true' or consent == 'True'
            
            # Use update_fields to bypass full model validation
            lead.save(update_fields=[
                'first_name', 'last_name', 'phone_number', 'email', 'pan_number',
                'gender', 'date_of_birth', 'city', 'state', 'pin_code', 'profession',
                'monthly_income', 'bureau_score', 'consent_taken', 'status', 'updated_at'
            ])
            
            return JsonResponse({
                'success': True,
                'message': 'Lead updated successfully'
            })
        except Lead.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Lead not found'}, status=404)
        except ValidationError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class LeadDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Delete a lead"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)
            lead_name = f"{lead.first_name} {lead.last_name}"
            lead.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Lead "{lead_name}" deleted successfully'
            })
        except Lead.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Lead not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
