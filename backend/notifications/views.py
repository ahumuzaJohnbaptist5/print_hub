from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import Notification

@login_required
def get_notifications(request):
    """API endpoint to fetch unread notifications."""
    notifications = Notification.objects.filter(
        user=request.user, 
        is_read=False
    ).order_by('-created_at')[:10]
    
    data = [{
        'id': n.id,
        'type': n.notification_type,
        'title': n.title,
        'message': n.message,
        'link': n.link,
        'created': n.created_at.strftime('%b %d, %H:%M'),
        'is_read': n.is_read,
    } for n in notifications]
    
    return JsonResponse({
        'notifications': data,
        'unread_count': len(data),
    })

@login_required
@require_POST
def mark_read(request, notification_id):
    """Mark a single notification as read."""
    Notification.objects.filter(
        id=notification_id, 
        user=request.user
    ).update(is_read=True)
    return JsonResponse({'status': 'ok'})

@login_required
@require_POST
def mark_all_read(request):
    """Mark all notifications as read."""
    Notification.objects.filter(
        user=request.user, 
        is_read=False
    ).update(is_read=True)
    return JsonResponse({'status': 'ok'})
