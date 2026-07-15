import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = 'admin'
email = 'printhub2027@gmail.com'
password = 'admin123'

# Check if user exists
if User.objects.filter(username=username).exists():
    # If exists, force them to be a superuser and update password
    user = User.objects.get(username=username)
    user.set_password(password)
    user.is_staff = True
    user.is_superuser = True
    user.save()
    print(f"✅ Updated existing user '{username}' to superuser with password '{password}'")
else:
    # If not exists, create new
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"✅ Created new superuser '{username}' with password '{password}'")
