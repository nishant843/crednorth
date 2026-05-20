from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse, StreamingHttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib import messages
import json
import csv
from crm_admin.models import UploadJob, UploadedLeadRow
from users.models import User
from crm_admin.tasks import process_lead_dedupe_push
from crm_admin.csv_parser import parse_csv_stream, bulk_insert_lead_rows


class Echo:
    """Simple write-through buffer for streaming csv.writer output."""
    def write(self, value):
        return value


def _wants_json_response(request):
    accept = request.headers.get('Accept', '')
    return 'application/json' in accept or request.headers.get('X-Requested-With') == 'XMLHttpRequest'


# Custom Error Handlers
def custom_404(request, exception):
    """Custom 404 error handler"""
    if _wants_json_response(request):
        return JsonResponse({'error': 'Not found'}, status=404)
    return render(request, '404.html', status=404)


def custom_500(request):
    """Custom 500 error handler"""
    if _wants_json_response(request):
        return JsonResponse({'error': 'Internal server error'}, status=500)
    return render(request, '500.html', status=500)


def custom_403(request, exception):
    """Custom 403 error handler"""
    if _wants_json_response(request):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    return render(request, '403.html', status=403)


def custom_400(request, exception):
    """Custom 400 error handler"""
    if _wants_json_response(request):
        return JsonResponse({'error': 'Bad request'}, status=400)
    return render(request, '400.html', status=400)


class HomeView(View):
    """Home page with navigation - accessible to all authenticated users"""
    def get(self, request):
        return render(request, 'home.html')


class LoginView(View):
    """Custom login view - Passwordless authentication (no password required)"""
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/')
        return render(request, 'login.html', {'no_password': True})
    
    def post(self, request):
        username = request.POST.get('username')  # This is phone_number
        next_url = request.POST.get('next', '/')
        
        # Passwordless authentication - only phone number required
        # Uses custom PasswordlessAuthBackend
        user = authenticate(request, username=username)
        
        if user is not None:
            login(request, user)
            
            # Try to get name from associated Lead, otherwise use phone number
            user_display_name = user.phone_number
            if hasattr(user, 'lead'):
                lead = user.user
                user_display_name = f"{lead.first_name} {lead.last_name}"
            
            messages.success(request, f'Welcome back, {user_display_name}!')
            # Redirect to default route or to the next URL
            if next_url and next_url != '/login/' and next_url != 'login':
                return redirect(next_url)
            else:
                return redirect('/')
        else:
            messages.error(request, 'Invalid phone number or user not active.')
            return render(request, 'login.html', {'no_password': True})


class LogoutView(View):
    """Logout view"""
    def get(self, request):
        logout(request)
        messages.success(request, 'You have been successfully logged out.')
        return redirect('login')


@method_decorator(login_required, name='dispatch')
class ProfileView(View):
    """User profile view - shows complete user information"""
    def get(self, request):
        user = request.user
        context = {
            'user': user,
        }
        return render(request, 'profile.html', context)


@method_decorator(login_required, name='dispatch')
@method_decorator(ensure_csrf_cookie, name='dispatch')
class DedupeAdminView(View):
    """Dedupe admin view - accessible to all authenticated users"""
    def get(self, request):
        return render(request, 'dedupe_admin.html')


@method_decorator(login_required, name='dispatch')
class BulkDedupeProcessView(View):
    """
    Handle bulk dedupe processing via Celery background task (async).
    NEW: Parses CSV immediately and stages rows in DB instead of using file paths.
    """
    def post(self, request):
        uploaded_file = request.FILES.get('file')
        lenders = request.POST.getlist('lenders')
        check_dedupe = request.POST.get('check_dedupe', 'false').lower() == 'true'
        send_leads = request.POST.get('send_leads', 'false').lower() == 'true'

        if not uploaded_file:
            return JsonResponse({'error': 'No file provided'}, status=400)

        if not lenders:
            return JsonResponse({'error': 'No lenders selected'}, status=400)

        try:
            job = UploadJob.objects.create(
                job_type=UploadJob.JOB_TYPE_LEAD_PROCESSING,
                status=UploadJob.STATUS_PENDING,
                lenders=json.dumps(lenders),
                check_dedupe=check_dedupe,
                send_leads=send_leads,
            )

            with parse_csv_stream(uploaded_file) as (reader, fieldnames):
                total_rows = bulk_insert_lead_rows(job, reader, fieldnames, batch_size=1000)

            UploadedLeadRow.objects.filter(upload_job=job).update(
                lender_selection=json.dumps(lenders)
            )

            task = process_lead_dedupe_push.delay(job.id)
            
            return JsonResponse({
                'success': True,
                'job_id': job.id,
                'task_id': task.id,
                'total_rows': total_rows,
                'message': 'CSV staged and processing queued'
            })

        except ValueError as exc:
            return JsonResponse({'error': f'CSV validation error: {str(exc)}'}, status=400)
        except Exception as exc:
            return JsonResponse({'error': f'Error processing upload: {str(exc)}'}, status=500)


@method_decorator(login_required, name='dispatch')
class DedupeProgressView(View):
    """Poll for lead processing progress (lightweight read-only)."""
    def get(self, request):
        job_id = request.GET.get('job_id')
        if not job_id:
            return JsonResponse({'error': 'No job_id provided'}, status=400)

        try:
            job = UploadJob.objects.get(pk=job_id)
        except UploadJob.DoesNotExist:
            return JsonResponse({'error': 'Job not found'}, status=404)
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=500)

        return JsonResponse({
            'success': True,
            'progress': {
                'job_id': job.id,
                'status': job.status,
                'total_rows': job.total_rows,
                'processed_rows': job.processed_rows,
                'percentage': job.percentage(),
                'current_batch': job.current_batch,
                'total_batches': job.total_batches,
                'success_count': job.success_count,
                'failed_count': job.failed_count,
                'is_done': job.is_complete(),
                'error_logs': job.error_logs if job.status == UploadJob.STATUS_FAILED else ''
            }
        })


@method_decorator(login_required, name='dispatch')
class DedupeDownloadResultsView(View):
    """Stream lead processing results CSV generated from UploadedLeadRow records."""

    CHUNK_SIZE = 2000

    def _csv_stream(self, upload_rows, user_files_map=None):
        writer = csv.writer(Echo())
        yield writer.writerow([
            'phone_number',
            'pan_number',
            'Files_name',
            'lender',
            'dedupe_result',
            'lender_response',
            'processing_status',
            'error_message',
            'processed_at',
        ])

        for lead_row in upload_rows.iterator(chunk_size=self.CHUNK_SIZE):
            lender_results = lead_row.lender_results or {}
            # Determine files_name: prefer staging `raw_data` field, fallback to mapped User.files_name
            raw_files_name = ''
            try:
                rd = lead_row.raw_data or {}
                # common CSV key variants
                raw_files_name = rd.get('Files_name') or rd.get('files_name') or rd.get('Files name') or rd.get('filesname') or ''
            except Exception:
                raw_files_name = ''

            user_files = ''
            if not raw_files_name and user_files_map is not None:
                user_files = user_files_map.get(lead_row.phone_number, '') or ''
            files_name_value = raw_files_name or user_files

            if lender_results:
                for lender, result in lender_results.items():
                    result = result or {}
                    yield writer.writerow([
                        lead_row.phone_number,
                        lead_row.pan_number,
                        files_name_value,
                        lender,
                        result.get('result', ''),
                        json.dumps(result, ensure_ascii=False),
                        lead_row.processing_status,
                        lead_row.error_message,
                        lead_row.processed_at.isoformat() if lead_row.processed_at else '',
                    ])
                continue

            # Rows with no lender result are still included for visibility.
            yield writer.writerow([
                lead_row.phone_number,
                lead_row.pan_number,
                files_name_value,
                '',
                '',
                '',
                lead_row.processing_status,
                lead_row.error_message,
                lead_row.processed_at.isoformat() if lead_row.processed_at else '',
            ])

    def get(self, request):
        job_id = request.GET.get('job_id')
        if not job_id:
            return JsonResponse({'error': 'No job_id provided'}, status=400)

        try:
            job = UploadJob.objects.get(pk=job_id)
        except UploadJob.DoesNotExist:
            return JsonResponse({'error': 'Job not found'}, status=404)

        if job.status != UploadJob.STATUS_COMPLETED:
            return JsonResponse({
                'error': f'Job status is {job.status}, not completed'
            }, status=400)

        queryset = UploadedLeadRow.objects.filter(upload_job=job).order_by('id')

        # Build a small map of phone_number -> User.files_name to enrich CSV rows when available.
        phones = list(queryset.values_list('phone_number', flat=True).distinct())
        user_files_map = {}
        if phones:
            users_qs = User.objects.filter(phone_number__in=phones).values('phone_number', 'files_name')
            user_files_map = {u['phone_number']: u.get('files_name') for u in users_qs}

        response = StreamingHttpResponse(
            self._csv_stream(queryset, user_files_map),
            content_type='text/csv'
        )
        response['Content-Disposition'] = f'attachment; filename="lead_processing_results_job_{job.id}.csv"'
        return response
