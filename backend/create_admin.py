import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = 'superadmin'
email = 'superadmin@example.com'
password = 'MyStrongPassword123!' # Change this to your desired password

if not User.objects.filter(username=username).exists():
    try:
        # We pass extra fields that your CustomUser model likely requires
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            email_verified=True,  # Added based on your migration name
            # station_id=None     # Uncomment and adjust if 'station' is strictly required
        )
        print(f"✅ SUCCESS: Superuser '{username}' created successfully!")
    except Exception as e:
        print(f"❌ FAILED to create superuser. Error: {e}")
        print("👉 Check the error above. You may need to add a missing field to this script.")
else:
    print(f"ℹ️ Superuser '{username}' already exists.")
