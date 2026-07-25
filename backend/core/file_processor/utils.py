# file_processor/utils.py
import os
import hashlib
from datetime import datetime

def generate_file_hash(file):
    """Generate SHA-256 hash of file"""
    hasher = hashlib.sha256()
    for chunk in file.chunks():
        hasher.update(chunk)
    return hasher.hexdigest()

def get_file_size_human(size):
    """Convert bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

def get_safe_filename(filename):
    """Sanitize filename"""
    return "".join(c for c in filename if c.isalnum() or c in '._- ')

def generate_unique_filename(original_name):
    """Generate unique filename with timestamp"""
    name, ext = os.path.splitext(original_name)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{name}_{timestamp}{ext}"
