import os
import django
import traceback

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = 'superadmin'
email = 'scholargrant22@gmail.com'
password = 'Ihategoogle@12' 

if not User.objects.filter(username=username).exists():
    try:
        # Removed email_verified. Django will handle standard superuser creation.
        user = User.objects.create_superuser(
            username=username, 
            email=email, 
            password=password
        )
        print(f"✅ SUCCESS: Superuser '{username}' created successfully!")
    except Exception as e:
        print(f"❌ FAILED to create superuser.")
        print(f"Error details: {e}")
        print("Full Traceback:")
        traceback.print_exc()
else:
    print(f"ℹ️ INFO: Superuser '{username}' already exists in the database.")
