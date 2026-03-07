"""
UI-based Bulk User Management View
Allows admins to perform bulk operations through web interface
Optimized for handling 1M+ users
"""
from django.shortcuts import render
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db import transaction
from django.core.cache import cache
from users.models import User
import uuid


class BulkUserManagementView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    UI-based bulk user management for CRM admins.
    Handles large datasets (1M+ users) efficiently.
    """
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request):
        """Display bulk management interface."""
        # Get counts for display
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        pending_users = User.objects.filter(status='pending').count()
        
        context = {
            'total_users': total_users,
            'active_users': active_users,
            'pending_users': pending_users,
        }
        
        return render(request, 'bulk_user_management.html', context)
    
    def post(self, request):
        """Handle bulk operations via AJAX with progress tracking."""
        import json
        
        action = request.POST.get('action')
        
        # Parse JSON body if present
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                action = data.get('action')
                filters = data.get('filters', {})
            except:
                data = request.POST
                filters = {}
        else:
            data = request.POST
            filters = data.get('filters', {})
        
        # Extract filter params
        if isinstance(filters, dict):
            filter_params = filters
        else:
            filter_params = {
                'status': request.POST.get('filter_status', ''),
                'profession': request.POST.get('filter_profession', ''),
                'is_active': request.POST.get('filter_is_active', ''),
                'min_income': request.POST.get('filter_min_income', ''),
                'max_income': request.POST.get('filter_max_income', ''),
                'min_bureau': request.POST.get('filter_min_bureau', ''),
                'max_bureau': request.POST.get('filter_max_bureau', ''),
            }
        
        # Generate unique operation ID for progress tracking
        operation_id = str(uuid.uuid4())
        
        # Build query
        query = User.objects.all()
        
        # Apply filters
        if filter_params['status']:
            query = query.filter(status=filter_params['status'])
        if filter_params['profession']:
            query = query.filter(profession=filter_params['profession'])
        if filter_params['is_active']:
            query = query.filter(is_active=filter_params['is_active'] == 'true')
        if filter_params['min_income']:
            query = query.filter(monthly_income__gte=float(filter_params['min_income']))
        if filter_params['max_income']:
            query = query.filter(monthly_income__lte=float(filter_params['max_income']))
        if filter_params['min_bureau']:
            query = query.filter(bureau_score__gte=int(filter_params['min_bureau']))
        if filter_params['max_bureau']:
            query = query.filter(bureau_score__lte=int(filter_params['max_bureau']))
        
        # Get count before action
        affected_count = query.count()
        
        if affected_count == 0:
            return JsonResponse({
                'success': False,
                'error': 'No users match the selected filters.'
            })
        
        # Security check: Prevent accidental deletion of all users
        if affected_count > 10000 and action == 'delete':
            return JsonResponse({
                'success': False,
                'error': f'Cannot delete {affected_count} users at once. Please use more specific filters or contact system administrator.'
            })
        
        # Perform action with batching (500 rows per batch)
        BATCH_SIZE = 500
        
        # Initialize progress tracking
        cache.set(f'bulk_operation_progress_{operation_id}', {
            'status': 'starting',
            'current_batch': 0,
            'total_batches': 0,
            'processed': 0,
            'total': affected_count,
            'action': action
        }, timeout=3600)  # 1 hour timeout
        
        try:
            if action == 'activate':
                updated_count = 0
                ids_to_update = list(query.values_list('id', flat=True))
                total_batches = (len(ids_to_update) + BATCH_SIZE - 1) // BATCH_SIZE
                
                # Update progress with total batches
                cache.set(f'bulk_operation_progress_{operation_id}', {
                    'status': 'processing',
                    'current_batch': 0,
                    'total_batches': total_batches,
                    'processed': 0,
                    'total': len(ids_to_update),
                    'action': action
                }, timeout=3600)
                
                for i in range(0, len(ids_to_update), BATCH_SIZE):
                    batch_ids = ids_to_update[i:i + BATCH_SIZE]
                    batch_num = (i // BATCH_SIZE) + 1
                    
                    updated_count += User.objects.filter(id__in=batch_ids).update(is_active=True)
                    
                    # Update progress after each batch
                    cache.set(f'bulk_operation_progress_{operation_id}', {
                        'status': 'processing',
                        'current_batch': batch_num,
                        'total_batches': total_batches,
                        'processed': min(i + BATCH_SIZE, len(ids_to_update)),
                        'total': len(ids_to_update),
                        'action': action
                    }, timeout=3600)
                
                message = f'Successfully activated {updated_count:,} users in {total_batches} batch(es).'
                
            elif action == 'deactivate':
                updated_count = 0
                ids_to_update = list(query.values_list('id', flat=True))
                total_batches = (len(ids_to_update) + BATCH_SIZE - 1) // BATCH_SIZE
                
                cache.set(f'bulk_operation_progress_{operation_id}', {
                    'status': 'processing',
                    'current_batch': 0,
                    'total_batches': total_batches,
                    'processed': 0,
                    'total': len(ids_to_update),
                    'action': action
                }, timeout=3600)
                
                for i in range(0, len(ids_to_update), BATCH_SIZE):
                    batch_ids = ids_to_update[i:i + BATCH_SIZE]
                    batch_num = (i // BATCH_SIZE) + 1
                    
                    updated_count += User.objects.filter(id__in=batch_ids).update(is_active=False)
                    
                    cache.set(f'bulk_operation_progress_{operation_id}', {
                        'status': 'processing',
                        'current_batch': batch_num,
                        'total_batches': total_batches,
                        'processed': min(i + BATCH_SIZE, len(ids_to_update)),
                        'total': len(ids_to_update),
                        'action': action
                    }, timeout=3600)
                
                message = f'Successfully deactivated {updated_count:,} users in {total_batches} batch(es).'
                
            elif action == 'mark_pending':
                updated_count = 0
                ids_to_update = list(query.values_list('id', flat=True))
                total_batches = (len(ids_to_update) + BATCH_SIZE - 1) // BATCH_SIZE
                
                cache.set(f'bulk_operation_progress_{operation_id}', {
                    'status': 'processing',
                    'current_batch': 0,
                    'total_batches': total_batches,
                    'processed': 0,
                    'total': len(ids_to_update),
                    'action': action
                }, timeout=3600)
                
                for i in range(0, len(ids_to_update), BATCH_SIZE):
                    batch_ids = ids_to_update[i:i + BATCH_SIZE]
                    batch_num = (i // BATCH_SIZE) + 1
                    
                    updated_count += User.objects.filter(id__in=batch_ids).update(status='pending')
                    
                    cache.set(f'bulk_operation_progress_{operation_id}', {
                        'status': 'processing',
                        'current_batch': batch_num,
                        'total_batches': total_batches,
                        'processed': min(i + BATCH_SIZE, len(ids_to_update)),
                        'total': len(ids_to_update),
                        'action': action
                    }, timeout=3600)
                
                message = f'Successfully marked {updated_count:,} users as pending in {total_batches} batch(es).'
                
            elif action == 'mark_approved':
                updated_count = 0
                ids_to_update = list(query.values_list('id', flat=True))
                total_batches = (len(ids_to_update) + BATCH_SIZE - 1) // BATCH_SIZE
                
                cache.set(f'bulk_operation_progress_{operation_id}', {
                    'status': 'processing',
                    'current_batch': 0,
                    'total_batches': total_batches,
                    'processed': 0,
                    'total': len(ids_to_update),
                    'action': action
                }, timeout=3600)
                
                for i in range(0, len(ids_to_update), BATCH_SIZE):
                    batch_ids = ids_to_update[i:i + BATCH_SIZE]
                    batch_num = (i // BATCH_SIZE) + 1
                    
                    updated_count += User.objects.filter(id__in=batch_ids).update(status='approved')
                    
                    cache.set(f'bulk_operation_progress_{operation_id}', {
                        'status': 'processing',
                        'current_batch': batch_num,
                        'total_batches': total_batches,
                        'processed': min(i + BATCH_SIZE, len(ids_to_update)),
                        'total': len(ids_to_update),
                        'action': action
                    }, timeout=3600)
                
                message = f'Successfully marked {updated_count:,} users as approved in {total_batches} batch(es).'
                
            elif action == 'mark_rejected':
                updated_count = 0
                ids_to_update = list(query.values_list('id', flat=True))
                total_batches = (len(ids_to_update) + BATCH_SIZE - 1) // BATCH_SIZE
                
                cache.set(f'bulk_operation_progress_{operation_id}', {
                    'status': 'processing',
                    'current_batch': 0,
                    'total_batches': total_batches,
                    'processed': 0,
                    'total': len(ids_to_update),
                    'action': action
                }, timeout=3600)
                
                for i in range(0, len(ids_to_update), BATCH_SIZE):
                    batch_ids = ids_to_update[i:i + BATCH_SIZE]
                    batch_num = (i // BATCH_SIZE) + 1
                    
                    updated_count += User.objects.filter(id__in=batch_ids).update(status='rejected')
                    
                    cache.set(f'bulk_operation_progress_{operation_id}', {
                        'status': 'processing',
                        'current_batch': batch_num,
                        'total_batches': total_batches,
                        'processed': min(i + BATCH_SIZE, len(ids_to_update)),
                        'total': len(ids_to_update),
                        'action': action
                    }, timeout=3600)
                
                message = f'Successfully marked {updated_count:,} users as rejected in {total_batches} batch(es).'
                
            elif action == 'delete':
                # Delete in batches for safety
                deleted_total = 0
                ids_to_delete = list(query.values_list('id', flat=True))
                total_batches = (len(ids_to_delete) + BATCH_SIZE - 1) // BATCH_SIZE
                
                cache.set(f'bulk_operation_progress_{operation_id}', {
                    'status': 'processing',
                    'current_batch': 0,
                    'total_batches': total_batches,
                    'processed': 0,
                    'total': len(ids_to_delete),
                    'action': action
                }, timeout=3600)
                
                for i in range(0, len(ids_to_delete), BATCH_SIZE):
                    batch_ids = ids_to_delete[i:i + BATCH_SIZE]
                    batch_num = (i // BATCH_SIZE) + 1
                    
                    User.objects.filter(id__in=batch_ids).delete()
                    deleted_total += len(batch_ids)
                    
                    cache.set(f'bulk_operation_progress_{operation_id}', {
                        'status': 'processing',
                        'current_batch': batch_num,
                        'total_batches': total_batches,
                        'processed': min(i + BATCH_SIZE, len(ids_to_delete)),
                        'total': len(ids_to_delete),
                        'action': action
                    }, timeout=3600)
                
                message = f'Successfully deleted {deleted_total:,} users in {total_batches} batch(es).'
                
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid action specified.'
                })
            
            # Mark operation as completed
            cache.set(f'bulk_operation_progress_{operation_id}', {
                'status': 'completed',
                'current_batch': 0,
                'total_batches': 0,
                'processed': affected_count,
                'total': affected_count,
                'action': action,
                'message': message
            }, timeout=3600)
            
            return JsonResponse({
                'success': True,
                'message': message,
                'affected_count': affected_count,
                'operation_id': operation_id
            })
            
        except Exception as e:
            # Mark operation as failed
            cache.set(f'bulk_operation_progress_{operation_id}', {
                'status': 'failed',
                'error': str(e),
                'action': action
            }, timeout=3600)
            
            return JsonResponse({
                'success': False,
                'error': f'Error performing bulk operation: {str(e)}',
                'operation_id': operation_id
            })


class BulkUserPreviewView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Preview users that will be affected by bulk operation.
    Helps prevent accidental mass operations.
    """
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request):
        """Return preview of users matching filters (GET method)."""
        return self._get_preview(request.GET)
    
    def post(self, request):
        """Return preview of users matching filters (POST method)."""
        return self._get_preview(request.POST)
    
    def _get_preview(self, params):
        """Shared logic for GET and POST preview."""
        filter_params = {
            'status': params.get('filter_status', ''),
            'profession': params.get('filter_profession', ''),
            'is_active': params.get('filter_is_active', ''),
            'min_income': params.get('filter_min_income', ''),
            'max_income': params.get('filter_max_income', ''),
            'min_bureau': params.get('filter_min_bureau', ''),
            'max_bureau': params.get('filter_max_bureau', ''),
        }
        
        # Build query
        query = User.objects.all()
        
        # Apply filters (same logic as BulkUserManagementView)
        if filter_params['status']:
            query = query.filter(status=filter_params['status'])
        if filter_params['profession']:
            query = query.filter(profession=filter_params['profession'])
        if filter_params['is_active']:
            query = query.filter(is_active=filter_params['is_active'] == 'true')
        if filter_params['min_income']:
            query = query.filter(monthly_income__gte=float(filter_params['min_income']))
        if filter_params['max_income']:
            query = query.filter(monthly_income__lte=float(filter_params['max_income']))
        if filter_params['min_bureau']:
            query = query.filter(bureau_score__gte=int(filter_params['min_bureau']))
        if filter_params['max_bureau']:
            query = query.filter(bureau_score__lte=int(filter_params['max_bureau']))
        
        # Get count and preview
        total_count = query.count()
        preview_users = list(query.values(
            'id', 'phone_number', 'first_name', 'last_name',
            'status', 'profession', 'monthly_income', 'is_active'
        )[:50])  # Show first 50 users
        
        return JsonResponse({
            'success': True,
            'total_count': total_count,
            'preview_users': preview_users,
            'showing': len(preview_users)
        })


class BulkOperationProgressView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Get real-time progress of bulk operations.
    Used for polling progress updates during long-running operations.
    """
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request):
        """Return current progress of operation."""
        operation_id = request.GET.get('operation_id')
        
        if not operation_id:
            return JsonResponse({
                'success': False,
                'error': 'No operation_id provided'
            })
        
        # Get progress from cache
        progress = cache.get(f'bulk_operation_progress_{operation_id}')
        
        if not progress:
            return JsonResponse({
                'success': False,
                'error': 'Operation not found or expired'
            })
        
        return JsonResponse({
            'success': True,
            'progress': progress
        })
