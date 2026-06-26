from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.contrib import messages

User = get_user_model()

def register_view(request):
    # If user is already logged in, redirect to dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role', 'student')
        
        # Validate fields
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
                role=role
            )
            messages.success(request, 'Registration successful! Please login.')
            return redirect('login')
        except Exception as e:
            return render(request, 'accounts/register.html', {'error': f'Registration failed: {str(e)}'})
    
    # GET request - show the form
    return render(request, 'accounts/register.html')


def login_view(request):
    # If user is already logged in, redirect to dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Authenticate user
        user = authenticate(username=username, password=password)
        
        if user is None:
            return render(request, 'accounts/login.html', {'error': 'Invalid credentials'})
        
        # Login successful
        login(request, user)
        messages.success(request, f'Welcome back, {username}!')
        return redirect('dashboard')
    
    # GET request - show the form
    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')