from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from stations.models import Station
from orders.models import Order
from orders.utils import send_welcome_email

User = get_user_model()

@login_required
def profile_view(request):
    past_orders = Order.objects.filter(client=request.user).order_by('-created_at')
    stations = Station.objects.all()

    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '').strip()
        request.user.last_name = request.POST.get('last_name', '').strip()
        request.user.phone_number = request.POST.get('phone_number', '').strip()
        
        station_id = request.POST.get('station')
        if station_id:
            request.user.station_id = station_id
        else:
            request.user.station = None
            
        request.user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')

    return render(request, 'accounts/profile.html', {
        'past_orders': past_orders,
        'stations': stations
    })

def register_view(request):
     next_url = request.GET.get('next', 'dashboard') 
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')

        if not username or not email or not password:
            return render(request, 'accounts/register.html', {'error': 'All fields are required'})

        if User.objects.filter(username=username).exists():
            return render(request, 'accounts/register.html', {'error': 'Username already exists'})

        if User.objects.filter(email=email).exists():
            return render(request, 'accounts/register.html', {'error': 'Email already exists'})

        try:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role='client',
                email_verified=True,
            )
            
            print(f"✅ User created: {username} ({email})")
            
            # Send welcome email with explicit error handling
            try:
                print(f"📧 Attempting to send welcome email to {email}...")
                send_welcome_email(user)
                print(f"✅ Welcome email sent successfully to {email}")
            except Exception as email_error:
                print(f"❌ Welcome email FAILED: {type(email_error).__name__}: {email_error}")
                import traceback
                traceback.print_exc()
                # Don't fail registration if email fails - user is already created
            
            messages.success(request, 'Account created successfully! Please log in.')
            return redirect('login')
            
        except Exception as e:
            print(f"❌ Registration FAILED: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return render(request, 'accounts/register.html', {'error': f'Registration failed: {str(e)}'})

    return render(request, 'accounts/register.html')

def login_view(request):
     next_url = request.GET.get('next', 'dashboard')
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(username=username, password=password)

        if user is None:
            return render(request, 'accounts/login.html', {'error': 'Invalid credentials'})
        
        login(request, user)
        messages.success(request, f'Welcome back, {user.first_name or username}!')
        return redirect('dashboard')

    return render(request, 'accounts/login.html')

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')
