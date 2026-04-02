from django.shortcuts import render, redirect
from django.views import View
from django.http import FileResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib import messages
import os
import tempfile
from loans.services.bulk_processor import process_csv


# Custom Error Handlers
def custom_404(request, exception):
    """Custom 404 error handler"""
    return render(request, '404.html', status=404)


def custom_500(request):
    """Custom 500 error handler"""
    return render(request, '500.html', status=500)


def custom_403(request, exception):
    """Custom 403 error handler"""
    return render(request, '403.html', status=403)


def custom_400(request, exception):
    """Custom 400 error handler"""
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
    """Handle bulk dedupe processing via standard Django view (non-DRF)."""
    def post(self, request):
        uploaded_file = request.FILES.get('file')
        lenders = request.POST.getlist('lenders')
        check_dedupe = request.POST.get('check_dedupe', 'false').lower() == 'true'
        send_leads = request.POST.get('send_leads', 'false').lower() == 'true'

        if not uploaded_file:
            return JsonResponse({'error': 'No file provided'}, status=400)

        if not lenders:
            return JsonResponse({'error': 'No lenders selected'}, status=400)

        input_fd, input_path = tempfile.mkstemp(suffix='.csv')
        output_fd, output_path = tempfile.mkstemp(suffix='.csv')

        try:
            with os.fdopen(input_fd, 'wb') as input_file:
                for chunk in uploaded_file.chunks():
                    input_file.write(chunk)

            os.close(output_fd)

            try:
                process_csv(input_path, output_path, lenders, check_dedupe, send_leads)
            except ValueError as exc:
                return JsonResponse({'error': str(exc)}, status=400)
            except Exception:
                return JsonResponse({'error': 'Processing failed'}, status=400)

            return FileResponse(
                open(output_path, 'rb'),
                as_attachment=True,
                filename='bulk_dedupe_results.csv'
            )

        except Exception:
            return JsonResponse({'error': 'File processing failed'}, status=400)
        finally:
            if os.path.exists(input_path):
                try:
                    os.unlink(input_path)
                except Exception:
                    pass
