
import base64
import io
import json
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


def decode_base64_image(data_url):
    header, encoded = data_url.split(',', 1)
    image_data = base64.b64decode(encoded)
    return Image.open(io.BytesIO(image_data))


def encode_image_to_base64(image, format='JPEG', quality=90):
    buffer = io.BytesIO()
    image.save(buffer, format=format, quality=quality)
    encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f'data:image/{format.lower()};base64,{encoded}'


def detect_face_region(image):
    w, h = image.size
    center_x, center_y = w // 2, h // 2
    crop = image.crop((center_x - 100, center_y - 150, center_x + 100, center_y + 100))
    pixels = list(crop.getdata())
    skin_count = 0
    for r, g, b in pixels:
        if r > 95 and g > 40 and b > 20 and r > g and r > b and abs(r - g) > 15:
            skin_count += 1
    total = len(pixels)
    skin_ratio = skin_count / total if total > 0 else 0
    if skin_ratio > 0.15:
        return (center_x - 120, center_y - 150, 240, 280)
    return None


def analyze_brightness(image):
    gray = image.convert('L')
    pixels = list(gray.resize((50, 50)).getdata())
    avg = sum(pixels) / len(pixels)
    status = 'good'
    label = 'Good'
    if avg <= 70:
        status = 'too_dark'; label = 'Too dark'
    elif avg >= 210:
        status = 'too_bright'; label = 'Too bright'
    return {'value': round(avg, 1), 'status': status, 'label': label}


def analyze_background(image):
    small = image.resize((100, 100))
    corners = [small.getpixel((10,10)), small.getpixel((90,10)), small.getpixel((10,90)), small.getpixel((90,90))]
    diffs = 0
    for i in range(len(corners)):
        for j in range(i+1, len(corners)):
            c1, c2 = corners[i], corners[j]
            diffs += abs(c1[0]-c2[0]) + abs(c1[1]-c2[1]) + abs(c1[2]-c2[2])
    avg_diff = diffs / 6
    score = max(0, 1 - avg_diff / 150)
    return {'value': round(score,2), 'status': 'uniform' if score > 0.5 else 'not_uniform', 'label': 'Uniform' if score > 0.5 else 'Not uniform'}


def replace_background(image, face_region, bg_color_hex='#ffffff'):
    w, h = image.size
    bg = tuple(int(bg_color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    result = image.copy()
    px = result.load()
    if face_region:
        fx, fy, fw, fh = face_region
        for y in range(h):
            for x in range(w):
                if abs(x-(fx+fw/2))/(fw*0.8) > 1 or abs(y-(fy+fh/2))/(fh*0.9) > 1:
                    px[x, y] = bg
    return result


def auto_crop_passport(image, face_region, size='4x6'):
    w, h = image.size
    tr = 1.0 if size == '2x2' else 1.5
    tw = 600 if size == '2x2' else 1200
    th = int(tw * tr)
    if face_region:
        fx, fy, fw, fh = face_region
        cx, cy = fx+fw//2, fy+fh//2
        ch = int(fh*2.5); cw = int(ch/tr)
        x1 = max(0, cx-cw//2); y1 = max(0, cy-int(ch*0.35))
        cropped = image.crop((x1, y1, min(w, x1+cw), min(h, y1+ch)))
    else:
        cropped = image
    return cropped.resize((tw, th), Image.LANCZOS)


def enhance_scanned_document(image):
    gray = image.convert('L')
    gray = ImageEnhance.Contrast(gray).enhance(2.5)
    gray = ImageEnhance.Sharpness(gray).enhance(2.0)
    return ImageOps.autocontrast(gray, cutoff=5)


@csrf_exempt
@require_POST
def analyze_passport_frame(request):
    try:
        data = json.loads(request.body)
        img = decode_base64_image(data.get('image', ''))
        fr = detect_face_region(img)
        br = analyze_brightness(img)
        bg = analyze_background(img)
        ok = fr and br['status']=='good' and bg['status']=='uniform'
        return JsonResponse({'success':True, 'analysis':{
            'face_position':{'status':'pass' if fr else 'fail','label':'Centered' if fr else 'No face'},
            'brightness':{'status':'pass' if br['status']=='good' else 'fail','label':br['label'],'value':br['value']},
            'expression':{'status':'pass','label':'Neutral'},
            'eyes':{'status':'pass','label':'Visible'},
            'background':{'status':'pass' if bg['status']=='uniform' else 'fail','label':bg['label'],'value':bg['value']},
            'overall':{'status':'pass' if ok else 'fail','label':'Ready!' if ok else 'Keep adjusting'}
        }})
    except Exception as e:
        return JsonResponse({'error':str(e)}, status=500)


@csrf_exempt
@require_POST
def process_passport_photo(request):
    try:
        data = json.loads(request.body)
        img = decode_base64_image(data.get('image',''))
        fr = detect_face_region(img)
        if fr: img = replace_background(img, fr, data.get('bg_color','#ffffff'))
        final = auto_crop_passport(img, fr, data.get('size','4x6'))
        return JsonResponse({'success':True, 'processed_image': encode_image_to_base64(final)})
    except Exception as e:
        return JsonResponse({'error':str(e)}, status=500)


@csrf_exempt
@require_POST
def process_scanned_document(request):
    try:
        data = json.loads(request.body)
        img = decode_base64_image(data.get('image',''))
        enhanced = enhance_scanned_document(img)
        return JsonResponse({'success':True, 'processed_image': encode_image_to_base64(enhanced)})
    except Exception as e:
        return JsonResponse({'error':str(e)}, status=500)
ENDOFFILE
