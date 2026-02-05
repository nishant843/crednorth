from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib import messages
import os


class HomeView(View):
    """Home page with navigation - accessible to all authenticated users"""
    def get(self, request):
        return render(request, 'home.html')


class LoginView(View):
    """Custom login view for all users"""
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/')
        return render(request, 'login.html')
    
    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        next_url = request.POST.get('next', '/')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            # Redirect to default route or to the next URL
            if next_url and next_url != '/login/' and next_url != 'login':
                return redirect(next_url)
            else:
                return redirect('/')
        else:
            messages.error(request, 'Invalid username or password.')
            return render(request, 'login.html')


class LogoutView(View):
    """Logout view"""
    def get(self, request):
        logout(request)
        messages.success(request, 'You have been successfully logged out.')
        return redirect('login')


@method_decorator(login_required, name='dispatch')
class DedupeAdminView(View):
    """Dedupe admin view - accessible to all authenticated users"""
    def get(self, request):
        return render(request, 'dedupe_admin.html')
