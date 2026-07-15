import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Check if admin exists
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser(
        username='admin',
        email='printhub2027@gmail.com',
        password='admin123'  # Change this immediately after first login!
    )
    print("✅ Superuser created! Username: admin, Password: admin123")
else:
    print("️ Superuser already exists")
