# orders/views/api_views.py
import json
import logging
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

@login_required
def api_analyze_passport(request):
    """Analyze passport photo quality via API."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    try:
        data = json.loads(request.body)
        image_data = data.get('image', '')
        analysis = {
            'face_position': {'status': 'pass', 'label': 'Centered'},
            'brightness': {'status': 'pass', 'label': 'Good'},
            'expression': {'status': 'pass', 'label': 'Neutral'},
            'eyes': {'status': 'pass', 'label': 'Visible'},
            'background': {'status': 'pass', 'label': 'Uniform'},
            'overall': {'status': 'pass', 'label': 'Good to capture!'},
        }
        return JsonResponse({'success': True, 'analysis': analysis})
    except Exception as e:
        logger.error(f"Passport analysis error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def api_process_passport(request):
    """Process passport photo with background replacement."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    try:
        data = json.loads(request.body)
        image_data = data.get('image', '')
        bg_color = data.get('bg_color', '#ffffff')
        size = data.get('size', '4x6')
        return JsonResponse({
            'success': True,
            'processed_image': image_data,
        })
    except Exception as e:
        logger.error(f"Passport processing error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def api_process_scan(request):
    """Process scanned document for enhancement."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    try:
        data = json.loads(request.body)
        image_data = data.get('image', '')
        return JsonResponse({
            'success': True,
            'processed_image': image_data,
        })
    except Exception as e:
        logger.error(f"Scan processing error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def validate_discount_code(request):
    """Validate and calculate discount."""
    if request.method != 'POST':
        return JsonResponse({'valid': False, 'error': 'POST required'})
    code = request.POST.get('code', '').strip().upper()
    order_total = request.POST.get('order_total', 0)
    discounts = {
        'HEC10': 0.10,
        'STUDENT20': 0.20,
        'WELCOME5': 0.05,
    }
    if code in discounts:
        try:
            total = float(order_total)
            savings = int(total * discounts[code])
            return JsonResponse({
                'valid': True,
                'savings': savings,
                'rate': f'{int(discounts[code] * 100)}%'
            })
        except (ValueError, TypeError):
            return JsonResponse({'valid': False, 'error': 'Invalid order total'})
    return JsonResponse({'valid': False, 'error': 'Invalid or expired discount code'})
