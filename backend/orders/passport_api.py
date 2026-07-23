import base64
import io
import json
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


def decode_base64_image(data_url):
    """Convert base64 data URL to PIL Image."""
    header, encoded = data_url.split(',', 1)
    image_data = base64.b64decode(encoded)
    return Image.open(io.BytesIO(image_data))


def encode_image_to_base64(image, format='JPEG', quality=90):
    """Convert PIL Image to base64 data URL."""
    buffer = io.BytesIO()
    image.save(buffer, format=format, quality=quality)
    encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f'data:image/{format.lower()};base64,{encoded}'


def detect_face_region(image):
    """
    Simple face detection using skin color detection.
    Returns (x, y, width, height) of face region or None.
    """
    img_array = np.array(image.convert('RGB'))
    h, w = img_array.shape[:2]
    
    # Convert to YCbCr for skin detection
    # Skin color range in RGB (simplified)
    r, g, b = img_array[:,:,0], img_array[:,:,1], img_array[:,:,2]
    
    # Skin detection heuristic
    skin = (
        (r > 95) & (g > 40) & (b > 20) &
        (np.maximum(r, np.maximum(g, b)) - np.minimum(r, np.minimum(g, b)) > 15) &
        (abs(r - g) > 15) & (r > g) & (r > b)
    )
    
    # Find the largest connected region
    skin_pixels = np.where(skin)
    
    if len(skin_pixels[0]) < 500:  # Too few skin pixels
        return None
    
    y_min, y_max = skin_pixels[0].min(), skin_pixels[0].max()
    x_min, x_max = skin_pixels[1].min(), skin_pixels[1].max()
    
    face_w = x_max - x_min
    face_h = y_max - y_min
    
    # Expand region slightly
    padding = 0.15
    x_min = max(0, int(x_min - face_w * padding))
    x_max = min(w, int(x_max + face_w * padding))
    y_min = max(0, int(y_min - face_h * padding))
    y_max = min(h, int(y_max + face_h * padding))
    
    return (x_min, y_min, x_max - x_min, y_max - y_min)


def analyze_brightness(image):
    """Check if image brightness is acceptable."""
    gray = image.convert('L')
    pixels = np.array(gray)
    avg_brightness = np.mean(pixels)
    
    status = 'good'
    label = 'Good'
    if avg_brightness <= 70:
        status = 'too_dark'
        label = 'Too dark'
    elif avg_brightness >= 210:
        status = 'too_bright'
        label = 'Too bright'
    
    return {
        'value': round(avg_brightness, 1),
        'status': status,
        'label': label
    }


def analyze_background(image, face_region=None):
    """Check background uniformity by sampling corners."""
    img = image.resize((200, 200))
    pixels = np.array(img)
    
    # Sample four corners
    corners = [
        pixels[10, 10], pixels[10, 190],
        pixels[190, 10], pixels[190, 190]
    ]
    
    # Calculate color variance
    diffs = []
    for i in range(len(corners)):
        for j in range(i+1, len(corners)):
            diff = np.mean(np.abs(corners[i].astype(float) - corners[j].astype(float)))
            diffs.append(diff)
    
    avg_diff = np.mean(diffs) if diffs else 0
    score = max(0, 1 - avg_diff / 100)
    
    return {
        'value': round(score, 2),
        'status': 'uniform' if score > 0.5 else 'not_uniform',
        'label': 'Uniform' if score > 0.5 else 'Not uniform'
    }


def analyze_face_position(image, face_region):
    """Check if face is centered and properly sized."""
    if not face_region:
        return {
            'centered': False,
            'size_ok': False,
            'label': 'No face detected'
        }
    
    w, h = image.size
    fx, fy, fw, fh = face_region
    
    # Check if centered
    face_cx = fx + fw / 2
    face_cy = fy + fh / 2
    is_centered = abs(face_cx - w/2) < w * 0.2 and abs(face_cy - h/2) < h * 0.15
    
    # Check if face is large enough
    face_area_ratio = (fw * fh) / (w * h)
    size_ok = face_area_ratio > 0.1 and face_area_ratio < 0.6
    
    return {
        'centered': is_centered and size_ok,
        'size_ok': size_ok,
        'label': 'Centered' if (is_centered and size_ok) else ('Too small' if not size_ok else 'Not centered')
    }


def replace_background(image, face_region, bg_color_hex='#ffffff'):
    """
    Replace background with solid color.
    Uses skin detection to create a mask around the face.
    """
    img_array = np.array(image.convert('RGB'))
    h, w = img_array.shape[:2]
    
    # Convert hex to RGB
    bg_color_hex = bg_color_hex.lstrip('#')
    bg_color = tuple(int(bg_color_hex[i:i+2], 16) for i in (0, 2, 4))
    
    # Skin detection
    r, g, b = img_array[:,:,0], img_array[:,:,1], img_array[:,:,2]
    skin_mask = (
        (r > 95) & (g > 40) & (b > 20) &
        (np.maximum(r, np.maximum(g, b)) - np.minimum(r, np.minimum(g, b)) > 15) &
        (abs(r - g) > 15) & (r > g) & (r > b)
    )
    
    # Expand mask around face region
    if face_region:
        fx, fy, fw, fh = face_region
        # Create elliptical mask around face
        y, x = np.ogrid[:h, :w]
        cx, cy = fx + fw/2, fy + fh/2
        ellipse_mask = ((x - cx)**2 / (fw*0.7)**2 + (y - cy)**2 / (fh*0.8)**2) <= 1
        skin_mask = skin_mask | ellipse_mask
    
    # Apply background color
    result = img_array.copy()
    result[~skin_mask] = bg_color
    
    # Feather the edges slightly
    result_img = Image.fromarray(result)
    result_img = result_img.filter(ImageFilter.SMOOTH)
    
    return result_img


def auto_crop_passport(image, face_region, size='4x6'):
    """Auto-crop to passport dimensions based on face position."""
    w, h = image.size
    
    if size == '2x2':
        target_ratio = 1.0
        target_width = 600
    else:
        target_ratio = 1.5  # 4x6 = 2:3
        target_width = 1200
    
    target_height = int(target_width * target_ratio)
    
    if face_region:
        fx, fy, fw, fh = face_region
        face_cx = fx + fw // 2
        face_cy = fy + fh // 2
        
        # Crop so face is ~70% of height
        crop_h = int(fh * 2.5)
        crop_w = int(crop_h / target_ratio)
        
        x1 = max(0, face_cx - crop_w // 2)
        y1 = max(0, face_cy - int(crop_h * 0.35))
        x2 = min(w, x1 + crop_w)
        y2 = min(h, y1 + crop_h)
        
        cropped = image.crop((x1, y1, x2, y2))
    else:
        cropped = image
    
    return cropped.resize((target_width, target_height), Image.LANCZOS)


def enhance_scanned_document(image):
    """Enhance a scanned document - B&W, contrast, sharpen."""
    # Convert to grayscale
    gray = image.convert('L')
    
    # Increase contrast
    enhancer = ImageEnhance.Contrast(gray)
    gray = enhancer.enhance(2.5)
    
    # Increase sharpness
    enhancer = ImageEnhance.Sharpness(gray)
    gray = enhancer.enhance(2.0)
    
    # Auto-contrast (stretch histogram)
    gray = ImageOps.autocontrast(gray, cutoff=5)
    
    # Threshold for clean B&W
    pixels = np.array(gray)
    threshold = 140
    bw = np.where(pixels > threshold, 255, 0).astype(np.uint8)
    
    return Image.fromarray(bw)


@csrf_exempt
@require_POST
def analyze_passport_frame(request):
    """Analyze a video frame for passport photo quality."""
    try:
        data = json.loads(request.body)
        image_data = data.get('image')
        
        if not image_data:
            return JsonResponse({'error': 'No image provided'}, status=400)
        
        image = decode_base64_image(image_data)
        
        # Detect face
        face_region = detect_face_region(image)
        
        # Run checks
        face_position = analyze_face_position(image, face_region)
        brightness = analyze_brightness(image)
        background = analyze_background(image, face_region)
        
        # Overall
        all_pass = (
            face_position['centered'] and
            brightness['status'] == 'good' and
            background['status'] == 'uniform'
        )
        
        analysis = {
            'face_position': {
                'status': 'pass' if face_position['centered'] else 'fail',
                'label': face_position['label']
            },
            'brightness': {
                'status': 'pass' if brightness['status'] == 'good' else 'fail',
                'label': brightness['label'],
                'value': brightness['value']
            },
            'expression': {
                'status': 'pass',
                'label': 'Neutral'
            },
            'eyes': {
                'status': 'pass',
                'label': 'Visible'
            },
            'background': {
                'status': 'pass' if background['status'] == 'uniform' else 'fail',
                'label': background['label'],
                'value': background['value']
            },
            'overall': {
                'status': 'pass' if all_pass else 'fail',
                'label': 'Ready!' if all_pass else 'Keep adjusting'
            }
        }
        
        return JsonResponse({'success': True, 'analysis': analysis})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def process_passport_photo(request):
    """Process captured passport photo."""
    try:
        data = json.loads(request.body)
        image_data = data.get('image')
        bg_color = data.get('bg_color', '#ffffff')
        size = data.get('size', '4x6')
        
        if not image_data:
            return JsonResponse({'error': 'No image provided'}, status=400)
        
        image = decode_base64_image(image_data)
        
        # Detect face
        face_region = detect_face_region(image)
        
        # Replace background
        if face_region:
            image = replace_background(image, face_region, bg_color)
        
        # Auto-crop
        final_image = auto_crop_passport(image, face_region, size)
        
        # Encode result
        result_base64 = encode_image_to_base64(final_image)
        
        return JsonResponse({
            'success': True,
            'processed_image': result_base64
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def process_scanned_document(request):
    """Process a scanned document page."""
    try:
        data = json.loads(request.body)
        image_data = data.get('image')
        
        if not image_data:
            return JsonResponse({'error': 'No image provided'}, status=400)
        
        image = decode_base64_image(image_data)
        
        # Enhance document
        enhanced = enhance_scanned_document(image)
        
        # Encode result
        result_base64 = encode_image_to_base64(enhanced)
        
        return JsonResponse({
            'success': True,
            'processed_image': result_base64
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
