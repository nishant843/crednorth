import os
import tempfile
import csv
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
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from users.models import User
from lenders.models import Lender
from crm_admin.models import UploadJob
from crm_admin.tasks import process_csv_upload


class CRMDashboardView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    CRM Dashboard for Leads management.
    Leads are PRIMARY - CSV uploads create Leads → auto-generate Users.
    """
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request):
        """Clean filter implementation - Manual submit only"""
        
        # === STEP 1: Get all filter parameters from GET request ===
        page = request.GET.get('page', 1)
        
        # Text filters
        name_filter = request.GET.get('name', '').strip()
        phone_filter = request.GET.get('phone', '').strip()
        pan_filter = request.GET.get('pan', '').strip()
        email_filter = request.GET.get('email', '').strip()
        city_filter = request.GET.get('city', '').strip()
        state_filter = request.GET.get('state', '').strip()
        pin_code_filter = request.GET.get('pin_code', '').strip()
        
        # Dropdown filters
        gender_filter = request.GET.get('gender', '').strip()
        profession_filter = request.GET.get('profession', '').strip()
        status_filter = request.GET.get('status', '').strip()
        
        # Range filters
        age_min = request.GET.get('age_min', '').strip()
        age_max = request.GET.get('age_max', '').strip()
        income_min = request.GET.get('income_min', '').strip()
        income_max = request.GET.get('income_max', '').strip()
        bureau_min = request.GET.get('bureau_min', '').strip()
        bureau_max = request.GET.get('bureau_max', '').strip()
        
        # === STEP 2: Start with base queryset ===
        users_query = User.objects.all()
        
        # === STEP 3: Apply each filter if provided ===
        
        # Name filter (first_name OR last_name)
        if name_filter:
            users_query = users_query.filter(
                Q(first_name__icontains=name_filter) | Q(last_name__icontains=name_filter)
            )
        
        # Phone filter
        if phone_filter:
            users_query = users_query.filter(phone_number__icontains=phone_filter)
        
        # PAN filter
        if pan_filter:
            users_query = users_query.filter(pan_number__icontains=pan_filter)
        
        # Email filter
        if email_filter:
            users_query = users_query.filter(email__icontains=email_filter)
        
        # City filter
        if city_filter:
            users_query = users_query.filter(city__icontains=city_filter)
        
        # State filter
        if state_filter:
            users_query = users_query.filter(state__icontains=state_filter)
        
        # Pin code filter - supports comma-separated values
        if pin_code_filter:
            # Split by comma and strip whitespace
            pin_codes = [pc.strip() for pc in pin_code_filter.split(',') if pc.strip()]
            # Only apply filter if we have valid pin codes after cleaning
            if pin_codes:
                if len(pin_codes) == 1:
                    # Single pincode - use icontains for partial match
                    users_query = users_query.filter(pin_code__icontains=pin_codes[0])
                else:
                    # Multiple pincodes - use exact match with __in
                    users_query = users_query.filter(pin_code__in=pin_codes)
        
        # Gender filter
        if gender_filter:
            users_query = users_query.filter(gender__iexact=gender_filter)
        
        # Profession filter
        if profession_filter:
            users_query = users_query.filter(profession__icontains=profession_filter)
        
        # Status filter
        if status_filter:
            users_query = users_query.filter(status=status_filter)
        
        # Age range filters
        if age_min:
            try:
                users_query = users_query.filter(age__gte=int(age_min))
            except (ValueError, TypeError):
                pass
        
        if age_max:
            try:
                users_query = users_query.filter(age__lte=int(age_max))
            except (ValueError, TypeError):
                pass
        
        # Income range filters
        if income_min:
            try:
                users_query = users_query.filter(monthly_income__gte=float(income_min))
            except (ValueError, TypeError):
                pass
        
        if income_max:
            try:
                users_query = users_query.filter(monthly_income__lte=float(income_max))
            except (ValueError, TypeError):
                pass
        
        # Bureau score range filters
        if bureau_min:
            try:
                users_query = users_query.filter(bureau_score__gte=int(bureau_min))
            except (ValueError, TypeError):
                pass
        
        if bureau_max:
            try:
                users_query = users_query.filter(bureau_score__lte=int(bureau_max))
            except (ValueError, TypeError):
                pass
        
        # === STEP 4: Order filtered results ===
        users_query = users_query.order_by('-created_at')
        
        # === STEP 5: Calculate statistics from filtered queryset ===
        filtered_count = users_query.count()
        filtered_with_consent = users_query.filter(consent_taken=True).count()
        filtered_high_bureau = users_query.filter(bureau_score__gte=750).count()
        filtered_pending = users_query.filter(status='pending').count()
        filtered_approved = users_query.filter(status='approved').count()
        filtered_rejected = users_query.filter(status='rejected').count()
        
        # === STEP 6: Paginate filtered results ===
        paginator = Paginator(users_query, 50)  # 50 users per page
        
        try:
            users_page = paginator.page(page)
        except PageNotAnInteger:
            users_page = paginator.page(1)
        except EmptyPage:
            users_page = paginator.page(paginator.num_pages)
        
        # === STEP 7: Get dropdown options (all available values) ===
        # Use predefined profession choices
        professions = ['Salaried', 'Self-Employed', 'Business']
        
        all_genders = User.objects.exclude(gender='').values_list('gender', flat=True).distinct()
        genders = sorted(set([g for g in all_genders if g]))
        
        # Get all lenders
        lenders = Lender.objects.all()
        
        # === STEP 8: Determine active page ===
        has_filters = bool(name_filter or phone_filter or pan_filter or email_filter or 
                          city_filter or state_filter or pin_code_filter or gender_filter or 
                          profession_filter or status_filter or age_min or age_max or 
                          income_min or income_max or bureau_min or bureau_max)
        
        if '/users/' in request.path or has_filters:
            active_page = 'users'
        else:
            active_page = 'overview'
        
        # === STEP 9: Build context dictionary ===
        context = {
            # Filtered user data
            'all_users': users_page,
            'users_page': users_page,
            'users': users_page,
            
            # Statistics from filtered queryset
            'total_users': filtered_count,
            'users_with_consent': filtered_with_consent,
            'high_bureau_users': filtered_high_bureau,
            'total_pending': filtered_pending,
            'total_approved': filtered_approved,
            'total_rejected': filtered_rejected,
            
            # Dropdown options
            'lenders': lenders,
            'professions': professions,
            'genders': genders,
            
            # Filter values (for preserving in form)
            'name_filter': name_filter,
            'phone_filter': phone_filter,
            'pan_filter': pan_filter,
            'email_filter': email_filter,
            'city_filter': city_filter,
            'state_filter': state_filter,
            'pin_code': pin_code_filter,
            'selected_gender': gender_filter,
            'selected_profession': profession_filter,
            'selected_status': status_filter,
            'age_min': age_min,
            'age_max': age_max,
            'income_min': income_min,
            'income_max': income_max,
            'bureau_min': bureau_min,
            'bureau_max': bureau_max,
            
            # Page state
            'active_page': active_page,
            'active_tab': 'users',
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
            from loans.services.lead_csv_processor import bulk_create_or_update_leads_from_csv
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
        users_query = User.objects.all()
        
        total_leads = users_query.count()
        leads_with_consent = users_query.filter(consent_taken=True).count()
        high_bureau_leads = users_query.filter(bureau_score__gte=750).count()
        total_pending = users_query.filter(status='pending').count()
        total_approved = users_query.filter(status='approved').count()
        total_rejected = users_query.filter(status='rejected').count()
        
        total_users = User.objects.count()
        users_with_consent = users_query.filter(consent_taken=True).count()
        high_bureau_users = users_query.filter(bureau_score__gte=750).count()
        
        context = {
            'total_users': total_leads,
            'users_with_consent': leads_with_consent,
            'high_bureau_users': high_bureau_leads,
            'total_pending': total_pending,
            'total_approved': total_approved,
            'total_rejected': total_rejected,
            'lenders': lenders,
            'total_users': total_users,
            'users_with_consent': users_with_consent,
            'high_bureau_users': high_bureau_users,
            'active_page': 'lenders',
        }
        
        return render(request, 'crm_dashboard.html', context)


class CRMFetchDataView(LoginRequiredMixin, UserPassesTestMixin, View):
    """CRM Fetch Data page - Upload CSV with phone numbers, download CSV with all user data"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request):
        # Get statistics for display
        users_query = User.objects.all()
        
        total_leads = users_query.count()
        leads_with_consent = users_query.filter(consent_taken=True).count()
        high_bureau_leads = users_query.filter(bureau_score__gte=750).count()
        total_pending = users_query.filter(status='pending').count()
        total_approved = users_query.filter(status='approved').count()
        total_rejected = users_query.filter(status='rejected').count()
        
        total_users = User.objects.count()
        users_with_consent = users_query.filter(consent_taken=True).count()
        high_bureau_users = users_query.filter(bureau_score__gte=750).count()
        
        lenders = Lender.objects.all()
        
        context = {
            'total_users': total_leads,
            'users_with_consent': leads_with_consent,
            'high_bureau_users': high_bureau_leads,
            'total_pending': total_pending,
            'total_approved': total_approved,
            'total_rejected': total_rejected,
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
            leads = User.objects.filter(phone_number__in=phone_numbers).select_related()
            
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


class LenderCreateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Create a new lender with optional pincode CSV upload"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request):
        try:
            # Create lender
            lender = Lender.objects.create(
                name=request.POST.get('name')
            )
            
            # Process pincode CSV if provided
            pincode_type = request.POST.get('pincode_type', '').strip()
            pincode_csv = request.FILES.get('pincode_csv')
            pincodes_added = 0
            
            if pincode_type and pincode_csv:
                # Validate pincode type
                if pincode_type not in ['whitelist', 'blacklist']:
                    lender.delete()  # Rollback lender creation
                    return JsonResponse({
                        'success': False, 
                        'error': 'Invalid pincode type. Must be "whitelist" or "blacklist"'
                    }, status=400)
                
                # Read and parse CSV
                try:
                    decoded_file = pincode_csv.read().decode('utf-8').splitlines()
                except UnicodeDecodeError:
                    pincode_csv.seek(0)
                    decoded_file = pincode_csv.read().decode('utf-8-sig').splitlines()
                
                csv_reader = csv.DictReader(decoded_file)
                
                # Check for required column
                if 'pincode' not in [col.lower().strip() for col in csv_reader.fieldnames]:
                    lender.delete()  # Rollback lender creation
                    return JsonResponse({
                        'success': False,
                        'error': 'CSV must have a column named "pincode"'
                    }, status=400)
                
                # Extract pincodes
                pincodes = set()
                for row in csv_reader:
                    # Find pincode column (case-insensitive)
                    pincode_value = None
                    for key, value in row.items():
                        if key.lower().strip() == 'pincode':
                            pincode_value = value.strip()
                            break
                    
                    if pincode_value:
                        # Validate pincode format (6 digits)
                        if pincode_value.isdigit() and len(pincode_value) == 6:
                            pincodes.add(pincode_value)
                
                if not pincodes:
                    lender.delete()  # Rollback lender creation
                    return JsonResponse({
                        'success': False,
                        'error': 'No valid pincodes found in CSV. Pincodes must be 6 digits.'
                    }, status=400)
                
                # Update lender with pincodes
                pincodes_list = sorted(list(pincodes))
                if pincode_type == 'whitelist':
                    lender.pincodes_whitelisted = pincodes_list
                else:  # blacklist
                    lender.pincodes_blacklisted = pincodes_list
                
                lender.save()
                pincodes_added = len(pincodes_list)
            
            response_data = {
                'success': True, 
                'lender_id': lender.id
            }
            
            if pincodes_added > 0:
                response_data['pincodes_added'] = pincodes_added
            
            return JsonResponse(response_data)
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class LenderDetailView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Get lender details for profile view"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def handle_no_permission(self):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    def get(self, request, lender_id):
        try:
            lender = Lender.objects.get(id=lender_id)
            
            data = {
                'success': True,
                'lender': {
                    'id': lender.id,
                    'name': lender.name,
                    'total_leads': lender.total_leads,
                    'total_approved': lender.total_approved,
                    'total_rejected': lender.total_rejected,
                    'total_sanctioned_loan_amount': str(lender.total_sanctioned_loan_amount),
                    'total_loan_amount_disbursed': str(lender.total_loan_amount_disbursed),
                    'total_kyc_pan': lender.total_kyc_pan,
                    'total_kyc_aadhar': lender.total_kyc_aadhar,
                    'pincodes_whitelisted': lender.pincodes_whitelisted,
                    'pincodes_blacklisted': lender.pincodes_blacklisted,
                    'mis_first_updated_date': lender.mis_first_updated_date.strftime('%Y-%m-%d') if lender.mis_first_updated_date else None,
                    'mis_first_updated_time': lender.mis_first_updated_time.strftime('%H:%M:%S') if lender.mis_first_updated_time else None,
                    'mis_last_updated_date': lender.mis_last_updated_date.strftime('%Y-%m-%d') if lender.mis_last_updated_date else None,
                    'mis_last_updated_time': lender.mis_last_updated_time.strftime('%H:%M:%S') if lender.mis_last_updated_time else None,
                    'mis_updated_by': lender.mis_updated_by.username if lender.mis_updated_by else None,
                    'created_at': lender.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'updated_at': lender.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                },
            }
            
            return JsonResponse(data)
        except Lender.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Lender not found'}, status=404)


class LenderUpdateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Update lender details"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def handle_no_permission(self):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    def post(self, request, lender_id):
        try:
            lender = Lender.objects.get(id=lender_id)
            
            # Update name if provided
            name = request.POST.get('name')
            if name:
                lender.name = name
            
            # Handle pincode CSV upload if provided
            pincode_type = request.POST.get('pincode_type', '').strip()
            pincode_csv = request.FILES.get('pincode_csv')
            pincodes_message = None
            
            if pincode_type and pincode_csv:
                # Validate pincode type
                valid_types = ['whitelist', 'blacklist']
                if pincode_type not in valid_types:
                    return JsonResponse({
                        'success': False, 
                        'error': f'Invalid pincode type. Must be one of: {", ".join(valid_types)}'
                    }, status=400)
                
                # Read and parse CSV
                try:
                    decoded_file = pincode_csv.read().decode('utf-8').splitlines()
                except UnicodeDecodeError:
                    pincode_csv.seek(0)
                    decoded_file = pincode_csv.read().decode('utf-8-sig').splitlines()
                
                csv_reader = csv.DictReader(decoded_file)
                
                # Check for required column
                if 'pincode' not in [col.lower().strip() for col in csv_reader.fieldnames]:
                    return JsonResponse({
                        'success': False,
                        'error': 'CSV must have a column named "pincode"'
                    }, status=400)
                
                # Extract pincodes
                new_pincodes = set()
                for row in csv_reader:
                    # Find pincode column (case-insensitive)
                    pincode_value = None
                    for key, value in row.items():
                        if key.lower().strip() == 'pincode':
                            pincode_value = value.strip()
                            break
                    
                    if pincode_value:
                        # Validate pincode format (6 digits)
                        if pincode_value.isdigit() and len(pincode_value) == 6:
                            new_pincodes.add(pincode_value)
                
                if not new_pincodes:
                    return JsonResponse({
                        'success': False,
                        'error': 'No valid pincodes found in CSV. Pincodes must be 6 digits.'
                    }, status=400)
                
                new_pincodes_list = sorted(list(new_pincodes))
                
                # Update lender pincodes based on type (replace only)
                if pincode_type == 'whitelist':
                    lender.pincodes_whitelisted = new_pincodes_list
                    pincodes_message = f'{len(new_pincodes_list)} pincodes replaced in whitelist'
                elif pincode_type == 'blacklist':
                    lender.pincodes_blacklisted = new_pincodes_list
                    pincodes_message = f'{len(new_pincodes_list)} pincodes replaced in blacklist'
            
            lender.save()
            
            response_data = {
                'success': True,
                'message': 'Lender updated successfully'
            }
            
            if pincodes_message:
                response_data['pincodes_updated'] = pincodes_message
            
            return JsonResponse(response_data)
            
        except Lender.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Lender not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class LenderDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Delete a lender"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def handle_no_permission(self):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    def post(self, request, lender_id):
        try:
            lender = Lender.objects.get(id=lender_id)
            lender_name = lender.name
            lender.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Lender "{lender_name}" deleted successfully'
            })
        except Lender.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Lender not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class CSVValidateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Validate CSV headers and size without storing rows in cache."""

    PHONE_ALIASES = {'phone_number', 'phone', 'mobile', 'mobile_number', 'contact', 'contact_number'}

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def post(self, request):
        return JsonResponse({
            'success': False,
            'error': 'UI bulk upload is temporarily disabled. Use: python manage.py import_leads <file_path>'
        }, status=503)

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return JsonResponse({'success': False, 'error': 'No file provided'}, status=400)

        try:
            decoded_file = uploaded_file.read().decode('utf-8-sig').splitlines()
            csv_reader = csv.DictReader(decoded_file)
            if not csv_reader.fieldnames:
                return JsonResponse({'success': False, 'error': 'CSV file is empty'}, status=400)

            normalized_headers = {
                ''.join(ch if ch.isalnum() else '_' for ch in header.lower()).strip('_')
                for header in csv_reader.fieldnames
                if header
            }
            has_phone = any(alias in normalized_headers for alias in self.PHONE_ALIASES)
            if not has_phone:
                return JsonResponse({
                    'success': False,
                    'error': 'Missing required phone column. Accepted: phone_number, phone, mobile'
                }, status=400)

            total_rows = sum(1 for _ in csv_reader)
            return JsonResponse({
                'success': True,
                'total_rows': total_rows,
                'headers': csv_reader.fieldnames,
            })
        except Exception as exc:
            return JsonResponse({'success': False, 'error': f'Error processing CSV: {exc}'}, status=400)


class BulkUploadView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Create an async UploadJob and enqueue CSV processing."""

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def post(self, request):
        return JsonResponse({
            'success': False,
            'error': 'UI bulk upload is temporarily disabled. Use: python manage.py import_leads <file_path>'
        }, status=503)

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return JsonResponse({'success': False, 'error': 'No file provided'}, status=400)

        if not uploaded_file.name.lower().endswith('.csv'):
            return JsonResponse({'success': False, 'error': 'Invalid file type. Please upload a CSV file.'}, status=400)

        try:
            job = UploadJob.objects.create(file=uploaded_file, status=UploadJob.STATUS_PENDING)
            process_csv_upload.delay(job.id)
            return JsonResponse({
                'success': True,
                'job_id': job.id,
                'status': job.status,
                'message': 'Upload job created and queued for processing.'
            })
        except Exception as exc:
            return JsonResponse({'success': False, 'error': f'Error creating upload job: {exc}'}, status=500)


class UploadProgressView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Return upload progress only; no processing happens here."""

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def get(self, request):
        return JsonResponse({
            'success': False,
            'error': 'Upload progress API is temporarily disabled for UI flow. Use management command import_leads.'
        }, status=503)

        job_id = request.GET.get('job_id')
        if not job_id:
            return JsonResponse({'success': False, 'error': 'No job_id provided'}, status=400)

        try:
            job = UploadJob.objects.get(pk=job_id)
        except UploadJob.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Upload job not found'}, status=404)
        except Exception as exc:
            return JsonResponse({'success': False, 'error': str(exc)}, status=500)

        percentage = 0
        if job.total_rows > 0:
            percentage = int((job.processed_rows / job.total_rows) * 100)

        return JsonResponse({
            'success': True,
            'progress': {
                'job_id': job.id,
                'status': job.status,
                'total_rows': job.total_rows,
                'processed_rows': job.processed_rows,
                'percentage': percentage,
                'is_done': job.status in [UploadJob.STATUS_COMPLETED, UploadJob.STATUS_FAILED],
            }
        })


class DownloadSampleCSVView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Download sample CSV template for bulk upload"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request):
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="sample_leads_upload.csv"'
        
        writer = csv.writer(response)
        
        # Write header row with all columns
        writer.writerow([
            'phone_number',  # Required
            'first_name',
            'last_name',
            'email',
            'pan_number',
            'date_of_birth',
            'gender',
            'pin_code',
            'city',
            'state',
            'profession',
            'monthly_income',
            'bureau_score'
        ])
        
        # Write sample data rows
        writer.writerow([
            '9876543210',
            'John',
            'Doe',
            'john.doe@example.com',
            'ABCDE1234F',
            '1990-01-15',
            'Male',
            '400001',
            'Mumbai',
            'Maharashtra',
            'Salaried',
            '50000',
            '750'
        ])
        
        writer.writerow([
            '9123456789',
            'Jane',
            'Smith',
            'jane.smith@example.com',
            'XYZAB5678Y',
            '1985-06-20',
            'Female',
            '110001',
            'Delhi',
            'Delhi',
            'Self-Employed',
            '75000',
            '800'
        ])
        
        writer.writerow([
            '9555555555',
            'Raj',
            'Kumar',
            'raj.kumar@example.com',
            'PQRST9012K',
            '1992-03-10',
            'Male',
            '560001',
            'Bangalore',
            'Karnataka',
            'Business',
            '60000',
            '720'
        ])
        
        return response


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
        users_query = User.objects.all()
        
        # Apply filters
        if status_filter:
            users_query = users_query.filter(status=status_filter)
        
        if profession_filter:
            users_query = users_query.filter(profession__icontains=profession_filter)
        
        if gender_filter:
            users_query = users_query.filter(gender__iexact=gender_filter)
        
        if income_min:
            try:
                users_query = users_query.filter(monthly_income__gte=float(income_min))
            except ValueError:
                pass
        
        if income_max:
            try:
                users_query = users_query.filter(monthly_income__lte=float(income_max))
            except ValueError:
                pass
        
        if pin_code_filter:
            users_query = users_query.filter(pin_code__icontains=pin_code_filter)
        
        if search_query:
            users_query = users_query.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(phone_number__icontains=search_query) |
                Q(pan_number__icontains=search_query) |
                Q(email__icontains=search_query)
            )
        
        # Apply new inline filters
        if name_filter:
            users_query = users_query.filter(
                Q(first_name__icontains=name_filter) |
                Q(last_name__icontains=name_filter)
            )
        
        if phone_filter:
            users_query = users_query.filter(phone_number__icontains=phone_filter)
        
        if pan_filter:
            users_query = users_query.filter(pan_number__icontains=pan_filter)
        
        if email_filter:
            users_query = users_query.filter(email__icontains=email_filter)
        
        if city_filter:
            users_query = users_query.filter(city__icontains=city_filter)
        
        if state_filter:
            users_query = users_query.filter(state__icontains=state_filter)
        
        if age_min:
            try:
                users_query = users_query.filter(age__gte=int(age_min))
            except ValueError:
                pass
        
        if age_max:
            try:
                users_query = users_query.filter(age__lte=int(age_max))
            except ValueError:
                pass
        
        if bureau_min:
            try:
                users_query = users_query.filter(bureau_score__gte=int(bureau_min))
            except ValueError:
                pass
        
        if bureau_max:
            try:
                users_query = users_query.filter(bureau_score__lte=int(bureau_max))
            except ValueError:
                pass
        
        # Get all matching leads
        leads = users_query.order_by('-created_at')
        
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


class LeadCreateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Create a new lead/user"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request):
        from django.core.exceptions import ValidationError
        try:
            # Only phone_number is required
            phone_number = request.POST.get('phone_number', '').strip()
            if not phone_number:
                return JsonResponse({'success': False, 'error': 'Phone number is required'}, status=400)
            
            # Clean phone number - remove any non-digit characters
            phone_number = ''.join(filter(str.isdigit, phone_number))
            if len(phone_number) != 10:
                return JsonResponse({'success': False, 'error': 'Phone number must be exactly 10 digits'}, status=400)
            
            # Check if user already exists
            if User.objects.filter(phone_number=phone_number).exists():
                return JsonResponse({'success': False, 'error': 'A user with this phone number already exists'}, status=400)
            
            # Create new user with only phone_number (required field)
            user = User(phone_number=phone_number)
            
            # Add optional fields if provided
            first_name = request.POST.get('first_name', '').strip()
            if first_name:
                user.first_name = first_name
            
            last_name = request.POST.get('last_name', '').strip()
            if last_name:
                user.last_name = last_name
            
            email = request.POST.get('email', '').strip()
            if email:
                user.email = email
            
            pan = request.POST.get('pan', '').strip().upper()
            if pan:
                user.pan_number = pan
            
            gender = request.POST.get('gender', '').strip()
            if gender:
                user.gender = gender
            
            pin_code = request.POST.get('pin_code', '').strip()
            if pin_code:
                user.pin_code = pin_code
            
            city = request.POST.get('city', '').strip()
            if city:
                user.city = city
            
            state = request.POST.get('state', '').strip()
            if state:
                user.state = state
            
            # Handle date of birth
            dob = request.POST.get('dob', '').strip()
            if dob:
                try:
                    from datetime import datetime
                    user.date_of_birth = datetime.strptime(dob, '%Y-%m-%d').date()
                    # Calculate age from DOB
                    from users.models import calculate_age_from_dob
                    user.age = calculate_age_from_dob(user.date_of_birth)
                except (ValueError, TypeError):
                    return JsonResponse({'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
            
            # Handle numeric fields
            income = request.POST.get('income', '').strip()
            if income:
                try:
                    user.monthly_income = float(income)
                except (ValueError, TypeError):
                    return JsonResponse({'success': False, 'error': 'Invalid income value'}, status=400)
            
            # Handle profession (employment_type from form)
            profession = request.POST.get('employment_type', '').strip()
            if profession:
                user.profession = profession
            
            # Handle status
            status_val = request.POST.get('status', 'pending').strip()
            user.status = status_val
            
            # Save the user
            user.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Lead created successfully with phone number {phone_number}'
            })
            
        except ValidationError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class LeadDetailView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Get lead details for profile view"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request, lead_id):
        try:
            lead = User.objects.get(id=lead_id)
            
            # Lead now contains all data, no need to fetch from User
            # User model only has authentication data (id, phone_number, password)
            user_data = None
            user_meta = None
            
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
            }
            
            return JsonResponse(data)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Lead not found'}, status=404)


class LeadUpdateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Update lead details"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request, lead_id):
        from django.core.exceptions import ValidationError
        try:
            lead = User.objects.get(id=lead_id)
            
            # Update fields from POST data
            lead.first_name = request.POST.get('first_name', lead.first_name)
            lead.last_name = request.POST.get('last_name', lead.last_name)
            
            # Validate phone number if being updated
            new_phone = request.POST.get('phone_number', '').strip()
            if new_phone and new_phone != lead.phone_number:
                # Clean phone number - remove any non-digit characters
                new_phone = ''.join(filter(str.isdigit, new_phone))
                if len(new_phone) != 10:
                    return JsonResponse({'success': False, 'error': 'Phone number must be exactly 10 digits'}, status=400)
                # Check if new phone number already exists
                if User.objects.filter(phone_number=new_phone).exclude(id=lead_id).exists():
                    return JsonResponse({'success': False, 'error': 'A user with this phone number already exists'}, status=400)
                lead.phone_number = new_phone
            
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
                try:
                    from datetime import datetime
                    lead.date_of_birth = datetime.strptime(dob, '%Y-%m-%d').date()
                    # Calculate age from DOB
                    from users.models import calculate_age_from_dob
                    lead.age = calculate_age_from_dob(lead.date_of_birth)
                except (ValueError, TypeError):
                    return JsonResponse({'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
            
            # Handle numeric fields
            monthly_income = request.POST.get('monthly_income')
            if monthly_income:
                try:
                    lead.monthly_income = float(monthly_income)
                except (ValueError, TypeError):
                    return JsonResponse({'success': False, 'error': 'Invalid monthly income value'}, status=400)
            
            bureau_score = request.POST.get('bureau_score')
            if bureau_score:
                try:
                    lead.bureau_score = int(bureau_score)
                except (ValueError, TypeError):
                    return JsonResponse({'success': False, 'error': 'Invalid bureau score value'}, status=400)
            
            # Handle consent
            consent = request.POST.get('consent_taken')
            lead.consent_taken = consent == 'true' or consent == 'True'
            
            # Use update_fields to bypass full model validation
            lead.save(update_fields=[
                'first_name', 'last_name', 'phone_number', 'email', 'pan_number',
                'gender', 'date_of_birth', 'age', 'city', 'state', 'pin_code', 'profession',
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
            lead = User.objects.get(id=lead_id)
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
