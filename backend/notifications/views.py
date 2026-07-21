import json
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Notification, PushSubscription

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
        'vapid_public_key': settings.VAPID_PUBLIC_KEY,
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

@login_required
@require_POST
def push_subscribe(request):
    """Save push notification subscription."""
    try:
        data = json.loads(request.body)
        subscription = data.get('subscription')
        
        if not subscription:
            return JsonResponse({'error': 'No subscription provided'}, status=400)
        
        PushSubscription.objects.update_or_create(
            user=request.user,
            endpoint=subscription.get('endpoint'),
            defaults={
                'p256dh': subscription.get('keys', {}).get('p256dh', ''),
                'auth': subscription.get('keys', {}).get('auth', ''),
            }
        )
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_POST
def push_unsubscribe(request):
    """Remove push notification subscription."""
    try:
        data = json.loads(request.body)
        endpoint = data.get('endpoint')
        if endpoint:
            PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def send_push_notification(user, title, body, url='/'):
    """Send push notification to a user's subscribed devices."""
    subscriptions = PushSubscription.objects.filter(user=user)
    
    for sub in subscriptions:
        try:
            from pywebpush import webpush, WebPushException
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {
                        'p256dh': sub.p256dh,
                        'auth': sub.auth,
                    }
                },
                data=json.dumps({
                    'title': title,
                    'body': body,
                    'url': url,
                }),
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{user.email or 'noreply@printlink.com'}"}
            )
        except Exception as e:
            print(f"Push failed for {user.username}: {e}")
            # Remove invalid subscriptions
            try:
                sub.delete()
            except:
                pass
